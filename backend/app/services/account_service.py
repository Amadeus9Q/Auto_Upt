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
    AccountSecretRevealResponse,
    AccountTestResponse,
    BilibiliCaptchaResponse,
    BilibiliLoginRequest,
    BilibiliLoginResponse,
    SavedCredentialOption,
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
        records["wechat"] = await self._active_account("wechat")
        wechat_saved_credentials = await self._wechat_saved_credentials()
        return AccountListResponse(
            accounts=[
                self._to_response(
                    adapter,
                    records.get(adapter.platform),
                    saved_credentials=wechat_saved_credentials if adapter.platform == "wechat" else None,
                )
                for adapter in list_adapters().values()
            ]
        )

    async def get_account(self, platform: str) -> AccountPlatformResponse:
        adapter = get_adapter(platform)
        records = await self._latest_accounts_by_platform()
        if platform == "wechat":
            records["wechat"] = await self._active_account("wechat")
        return self._to_response(
            adapter,
            records.get(platform),
            saved_credentials=await self._wechat_saved_credentials() if platform == "wechat" else None,
        )

    async def connect_wechat(self, request: WechatConnectRequest) -> AccountPlatformResponse:
        if self.session is None:
            raise RuntimeError("AccountService.connect_wechat requires a database session.")
        app_id = request.app_id.strip()
        app_secret = (request.app_secret or "").strip()
        record = await self._resolve_wechat_record_for_login(request.account_id, app_id)

        if not app_secret:
            if record is None:
                raise PlatformClientError(
                    "请选择已有公众号 AppID，或输入新的 AppSecret。",
                    platform_code="WECHAT_SECRET_REQUIRED",
                    next_action="请选择历史 AppID 或填写 AppSecret 后重新登录。",
                )
            credentials = self.cipher.decrypt_json(record.encrypted_credentials)
            saved_app_id = str(credentials.get("app_id") or record.external_user_id or "").strip()
            saved_secret = str(credentials.get("app_secret") or "").strip()
            if saved_app_id != app_id or not saved_secret:
                raise PlatformClientError(
                    "历史公众号凭据不完整，无法复用。",
                    platform_code="WECHAT_SAVED_SECRET_MISSING",
                    next_action="请重新输入 AppSecret 并登录。",
                )
            app_secret = saved_secret

        token_payload: dict[str, Any] = {}
        token_expires_at: datetime | None = None
        if request.test_connection:
            token_payload = await WechatOfficialAccountClient().get_access_token(
                app_id,
                app_secret,
            )
            token_expires_at = datetime.now(UTC) + timedelta(
                seconds=max(int(token_payload.get("expires_in", 7200)) - 300, 60)
            )

        encrypted_credentials = self.cipher.encrypt_json(
            {
                "app_id": app_id,
                "app_secret": app_secret,
                "access_token": token_payload.get("access_token"),
            }
        )
        base_credential_metadata = (record.credential_metadata or {}) if record else {}
        credential_metadata = {
            **base_credential_metadata,
            "active": True,
            "token_tested": request.test_connection,
        }
        if record is None:
            record = ConnectedAccountRecord(
                platform="wechat",
                display_name=request.display_name or "微信公众号",
                status="connected",
                auth_type="app_secret",
                external_user_id=app_id,
                encrypted_credentials=encrypted_credentials,
                credential_metadata=credential_metadata,
                token_expires_at=token_expires_at,
            )
            self.session.add(record)
        else:
            record.display_name = request.display_name or "微信公众号"
            record.status = "connected"
            record.auth_type = "app_secret"
            record.external_user_id = app_id
            record.encrypted_credentials = encrypted_credentials
            record.credential_metadata = credential_metadata
            record.token_expires_at = token_expires_at
        await self._mark_active_account(record, "wechat")
        await self.session.commit()
        await self.session.refresh(record)
        return self._to_response(
            get_adapter("wechat"),
            record,
            saved_credentials=await self._wechat_saved_credentials(),
        )

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
        record = ConnectedAccountRecord(
            platform="bilibili",
            display_name=request.display_name or nav_data.get("uname") or "B站账号",
            status="connected",
            auth_type="cookie",
            external_user_id=str(nav_data.get("mid") or cookies.get("DedeUserID") or ""),
            encrypted_credentials=self.cipher.encrypt_json(cookies),
            credential_metadata={
                "login_method": "password",
                "nav_checked": bool(nav_payload),
            },
            token_expires_at=None,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return BilibiliLoginResponse(
            account=self._to_response(get_adapter("bilibili"), record),
            message="B站登录成功，Cookie 凭据已加密保存。",
        )

    async def test_account(self, platform: str) -> AccountTestResponse:
        if self.session is None:
            raise RuntimeError("AccountService.test_account requires a database session.")
        record = await self._active_account("wechat") if platform == "wechat" else await self._get_latest_account(platform)
        if record is None:
            return AccountTestResponse(
                account=self._to_response(
                    get_adapter(platform),
                    None,
                    saved_credentials=await self._wechat_saved_credentials() if platform == "wechat" else None,
                ),
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
            if platform == "wechat":
                record.credential_metadata = {
                    **(record.credential_metadata or {}),
                    "active": False,
                }
            await self.session.commit()
            return AccountTestResponse(
                account=self._to_response(
                    get_adapter(platform),
                    record,
                    saved_credentials=await self._wechat_saved_credentials() if platform == "wechat" else None,
                ),
                ok=False,
                message=str(exc),
                details=self._redact_token_payload(getattr(exc, "details", {})),
            )

        record.status = "connected"
        if platform == "wechat":
            record.credential_metadata = {
                **(record.credential_metadata or {}),
                "active": True,
            }
        await self.session.commit()
        await self.session.refresh(record)
        return AccountTestResponse(
            account=self._to_response(
                get_adapter(platform),
                record,
                saved_credentials=await self._wechat_saved_credentials() if platform == "wechat" else None,
            ),
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

    async def reveal_account_secret(self, account_id: str) -> AccountSecretRevealResponse | None:
        if self.session is None:
            raise RuntimeError("AccountService.reveal_account_secret requires a database session.")
        record = await self.session.get(ConnectedAccountRecord, account_id)
        if record is None:
            return None
        if record.platform != "wechat":
            raise PlatformClientError(
                "当前仅支持查看公众号 AppSecret。",
                platform_code="SECRET_REVEAL_UNSUPPORTED",
            )
        if record.status != "connected":
            raise PlatformClientError(
                "公众号账号未连接，无法查看 AppSecret。",
                platform_code="WECHAT_ACCOUNT_NOT_CONNECTED",
                next_action="请重新输入 AppSecret 并登录。",
            )
        credentials = self.cipher.decrypt_json(record.encrypted_credentials)
        app_id = str(credentials.get("app_id") or record.external_user_id or "").strip()
        app_secret = str(credentials.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            raise PlatformClientError(
                "公众号凭据不完整，无法查看 AppSecret。",
                platform_code="WECHAT_SECRET_MISSING",
                next_action="请重新输入 AppSecret 并登录。",
            )
        return AccountSecretRevealResponse(
            account_id=record.id,
            platform="wechat",
            app_id=app_id,
            app_secret=app_secret,
        )

    async def get_record(self, account_id: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService.get_record requires a database session.")
        return await self.session.get(ConnectedAccountRecord, account_id)

    def decrypt_credentials(self, record: ConnectedAccountRecord) -> dict[str, Any]:
        return self.cipher.decrypt_json(record.encrypted_credentials)

    async def _latest_accounts_by_platform(self) -> dict[str, ConnectedAccountRecord]:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord).order_by(
                ConnectedAccountRecord.updated_at.desc(),
                ConnectedAccountRecord.created_at.desc(),
            )
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
            .order_by(ConnectedAccountRecord.updated_at.desc(), ConnectedAccountRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _active_account(self, platform: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord)
            .where(
                ConnectedAccountRecord.platform == platform,
                ConnectedAccountRecord.status == "connected",
            )
            .order_by(ConnectedAccountRecord.updated_at.desc(), ConnectedAccountRecord.created_at.desc())
        )
        for record in result.scalars().all():
            if (record.credential_metadata or {}).get("active") is True:
                return record
        return None

    async def _get_wechat_account_by_app_id(self, app_id: str) -> ConnectedAccountRecord | None:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord)
            .where(
                ConnectedAccountRecord.platform == "wechat",
                ConnectedAccountRecord.external_user_id == app_id,
            )
            .order_by(ConnectedAccountRecord.updated_at.desc(), ConnectedAccountRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _resolve_wechat_record_for_login(
        self,
        account_id: str | None,
        app_id: str,
    ) -> ConnectedAccountRecord | None:
        if account_id:
            record = await self.get_record(account_id)
            if record is None or record.platform != "wechat":
                raise PlatformClientError(
                    "选择的公众号历史凭据不存在。",
                    platform_code="WECHAT_ACCOUNT_NOT_FOUND",
                    next_action="请刷新账号列表后重试。",
                )
            if record.external_user_id != app_id:
                raise PlatformClientError(
                    "选择的历史凭据与当前 AppID 不匹配。",
                    platform_code="WECHAT_ACCOUNT_MISMATCH",
                    next_action="请重新选择 AppID。",
                )
            return record
        return await self._get_wechat_account_by_app_id(app_id)

    async def _wechat_saved_credentials(self) -> list[SavedCredentialOption]:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord)
            .where(
                ConnectedAccountRecord.platform == "wechat",
                ConnectedAccountRecord.status == "connected",
            )
            .order_by(ConnectedAccountRecord.updated_at.desc(), ConnectedAccountRecord.created_at.desc())
        )
        options: list[SavedCredentialOption] = []
        seen_app_ids: set[str] = set()
        for record in result.scalars().all():
            app_id = (record.external_user_id or "").strip()
            if not app_id or app_id in seen_app_ids:
                continue
            seen_app_ids.add(app_id)
            options.append(
                SavedCredentialOption(
                    account_id=record.id,
                    app_id=app_id,
                    display_name=record.display_name,
                    status=record.status,
                    has_secret=bool(record.encrypted_credentials),
                    is_active=(record.credential_metadata or {}).get("active") is True,
                    token_expires_at=record.token_expires_at,
                )
            )
        return options

    async def _mark_active_account(self, active_record: ConnectedAccountRecord, platform: str) -> None:
        if self.session is None:
            raise RuntimeError("AccountService requires a database session.")
        result = await self.session.execute(
            select(ConnectedAccountRecord).where(ConnectedAccountRecord.platform == platform)
        )
        for record in result.scalars().all():
            if record is active_record:
                continue
            metadata = dict(record.credential_metadata or {})
            if metadata.get("active") is True:
                metadata["active"] = False
                record.credential_metadata = metadata

    @staticmethod
    def _to_response(
        adapter: PlatformAdapter,
        record: ConnectedAccountRecord | None,
        saved_credentials: list[SavedCredentialOption] | None = None,
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
            saved_credentials=saved_credentials or [],
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
