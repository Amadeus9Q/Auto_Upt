from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.clients import BilibiliWebClient, PlatformClientError, WechatOfficialAccountClient
from backend.app.adapters.registry import get_adapter, list_adapters
from backend.app.core.security import CredentialCipher
from backend.app.models.account import ConnectedAccountRecord
from backend.app.schemas.account import (
    AccountListResponse,
    AccountPlatformResponse,
    AccountTestResponse,
    BilibiliCaptchaResponse,
    BilibiliLoginRequest,
    BilibiliLoginResponse,
    WechatConnectRequest,
)


class AccountService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.cipher = CredentialCipher()

    async def list_accounts(self) -> AccountListResponse:
        if self.session is None:
            raise RuntimeError("AccountService.list_accounts requires a database session.")
        records = await self._latest_accounts_by_platform()
        return AccountListResponse(
            accounts=[
                self._to_response(adapter, records.get(adapter.platform))
                for adapter in list_adapters().values()
            ]
        )

    async def get_account(self, platform: str) -> AccountPlatformResponse:
        adapter = get_adapter(platform)
        records = await self._latest_accounts_by_platform()
        return self._to_response(adapter, records.get(platform))

    async def connect_wechat(self, request: WechatConnectRequest) -> AccountPlatformResponse:
        if self.session is None:
            raise RuntimeError("AccountService.connect_wechat requires a database session.")
        token_payload: dict[str, Any] = {}
        token_expires_at: datetime | None = None
        if request.test_connection:
            token_payload = await WechatOfficialAccountClient().get_access_token(
                request.app_id,
                request.app_secret,
            )
            token_expires_at = datetime.now(UTC) + timedelta(
                seconds=max(int(token_payload.get("expires_in", 7200)) - 300, 60)
            )

        encrypted = self.cipher.encrypt_json(
            {
                "app_id": request.app_id,
                "app_secret": request.app_secret,
                "access_token": token_payload.get("access_token"),
            }
        )

        # UPSERT：如果该平台已有连接记录则更新，否则新建
        record = await self._upsert_account(
            platform="wechat",
            display_name=request.display_name or "微信公众号",
            auth_type="app_secret",
            external_user_id=request.app_id,
            encrypted_credentials=encrypted,
            credential_metadata={"token_tested": request.test_connection},
            token_expires_at=token_expires_at,
        )
        return self._to_response(get_adapter("wechat"), record)

    async def get_bilibili_captcha(self) -> BilibiliCaptchaResponse:
        captcha = await BilibiliWebClient().get_captcha()
        return BilibiliCaptchaResponse(
            gt=captcha["gt"],
            challenge=captcha["challenge"],
            token=captcha["token"],
        )

    async def login_bilibili(self, request: BilibiliLoginRequest) -> BilibiliLoginResponse:
        if self.session is None:
            raise RuntimeError("AccountService.login_bilibili requires a database session.")

        client = BilibiliWebClient()
        key_payload = await client.get_web_key()
        encrypted_password = client.encrypt_password(
            request.password,
            key_payload["public_key"],
            key_payload["salt"],
        )
        login_payload = await client.password_login(
            request.username,
            encrypted_password,
            request.token,
            request.challenge,
            request.geetest_validate,
            request.seccode,
        )
        cookies = login_payload["cookies"]

        nav_payload: dict[str, Any] = {}
        try:
            nav_payload = await client.nav_info(cookies)
        except PlatformClientError:
            # 登录接口已经返回 Cookie 时先保存账号，后续 /test 可单独验证 Cookie 是否可用。
            nav_payload = {}

        nav_data = nav_payload.get("data") or {}
        encrypted = self.cipher.encrypt_json(cookies)

        # UPSERT：如果该平台已有连接记录则更新 Cookie，否则新建
        record = await self._upsert_account(
            platform="bilibili",
            display_name=request.display_name or nav_data.get("uname") or "B站账号",
            auth_type="cookie",
            external_user_id=str(nav_data.get("mid") or cookies.get("DedeUserID") or ""),
            encrypted_credentials=encrypted,
            credential_metadata={
                "login_method": "password",
                "nav_checked": bool(nav_payload),
            },
            token_expires_at=None,
        )
        return BilibiliLoginResponse(
            account=self._to_response(get_adapter("bilibili"), record),
            message="B站登录成功，Cookie 凭据已加密保存。",
        )

    async def test_account(self, platform: str) -> AccountTestResponse:
        if self.session is None:
            raise RuntimeError("AccountService.test_account requires a database session.")
        record = await self._get_latest_account(platform)
        if record is None:
            return AccountTestResponse(
                account=self._to_response(get_adapter(platform), None),
                ok=False,
                message="账号尚未连接。",
                details={},
            )

        credentials = self.cipher.decrypt_json(record.encrypted_credentials)
        try:
            if platform == "wechat":
                details = await WechatOfficialAccountClient().get_access_token(
                    credentials.get("app_id", ""),
                    credentials.get("app_secret", ""),
                )
            elif platform == "bilibili":
                details = await BilibiliWebClient().nav_info(credentials)
            else:
                raise PlatformClientError(
                    f"{platform} real account testing is not supported.",
                    platform_code="UNSUPPORTED_PLATFORM",
                )
        except Exception as exc:
            record.status = "error"
            await self.session.commit()
            return AccountTestResponse(
                account=self._to_response(get_adapter(platform), record),
                ok=False,
                message=str(exc),
                details=self._redact_token_payload(getattr(exc, "details", {})),
            )

        record.status = "connected"
        await self.session.commit()
        await self.session.refresh(record)
        return AccountTestResponse(
            account=self._to_response(get_adapter(platform), record),
            ok=True,
            message="账号连接测试通过。",
            details=self._redact_token_payload(details),
        )

    async def disconnect_account(self, account_id: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService.disconnect_account requires a database session.")
        record = await self.session.get(ConnectedAccountRecord, account_id)
        if record is None:
            return None
        await self.session.delete(record)
        await self.session.commit()
        return record

    async def get_record(self, account_id: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService.get_record requires a database session.")
        return await self.session.get(ConnectedAccountRecord, account_id)

    def decrypt_credentials(self, record: ConnectedAccountRecord) -> dict[str, Any]:
        return self.cipher.decrypt_json(record.encrypted_credentials)

    async def _upsert_account(
        self,
        platform: str,
        display_name: str,
        auth_type: str,
        external_user_id: str,
        encrypted_credentials: str,
        credential_metadata: dict[str, Any],
        token_expires_at: datetime | None,
    ) -> ConnectedAccountRecord:
        """对同一平台执行 UPSERT：有则更新，无则新建。

        避免重复连接同一个平台时产生多条僵尸记录。
        """
        if self.session is None:
            raise RuntimeError("AccountService._upsert_account requires a database session.")
        existing = await self._get_latest_account(platform)
        if existing is not None:
            existing.display_name = display_name
            existing.status = "connected"
            existing.auth_type = auth_type
            existing.external_user_id = external_user_id
            existing.encrypted_credentials = encrypted_credentials
            existing.credential_metadata = credential_metadata
            existing.token_expires_at = token_expires_at
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        record = ConnectedAccountRecord(
            platform=platform,
            display_name=display_name,
            status="connected",
            auth_type=auth_type,
            external_user_id=external_user_id,
            encrypted_credentials=encrypted_credentials,
            credential_metadata=credential_metadata,
            token_expires_at=token_expires_at,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def _latest_accounts_by_platform(self) -> dict[str, ConnectedAccountRecord]:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord).order_by(ConnectedAccountRecord.created_at.desc())
        )
        records: dict[str, ConnectedAccountRecord] = {}
        for record in result.scalars().all():
            records.setdefault(record.platform, record)
        return records

    async def _get_latest_account(self, platform: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord)
            .where(ConnectedAccountRecord.platform == platform)
            .order_by(ConnectedAccountRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_response(
        adapter: PlatformAdapter,
        record: ConnectedAccountRecord | None,
    ) -> AccountPlatformResponse:
        capabilities = adapter.capabilities()
        auth = capabilities.get("auth", {})
        publish_modes = capabilities.get("publish_modes", [])
        real_publish_supported = adapter.platform in {"wechat", "bilibili"} and any(
            mode in publish_modes for mode in ("draft", "publish")
        )

        return AccountPlatformResponse(
            account_id=record.id if record else None,
            platform=adapter.platform,
            display_name=record.display_name if record else adapter.display_name,
            status=record.status if record else "not_configured",
            auth_type=record.auth_type if record else auth.get("type", "unknown"),
            real_publish_supported=real_publish_supported,
            required_for_real_publish=auth.get("required_for_real_publish", True),
            capabilities=capabilities,
            external_user_id=record.external_user_id if record else None,
            token_expires_at=record.token_expires_at if record else None,
            message=(
                "账号已连接，可用于真实发布。"
                if record and record.status == "connected"
                else "账号尚未连接，真实发布前需要完成授权或登录。"
            ),
        )

    @classmethod
    def _redact_token_payload(cls, payload: Any) -> Any:
        if isinstance(payload, dict):
            sensitive = {
                "access_token",
                "refresh_token",
                "app_secret",
                "SESSDATA",
                "bili_jct",
                "password",
            }
            return {
                key: ("***" if key in sensitive and value else cls._redact_token_payload(value))
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [cls._redact_token_payload(item) for item in payload]
        return payload
