from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.clients import BilibiliOpenPlatformClient, PlatformClientError, WechatOfficialAccountClient
from backend.app.adapters.registry import get_adapter, list_adapters
from backend.app.core.security import CredentialCipher
from backend.app.models.account import ConnectedAccountRecord
from backend.app.schemas.account import (
    AccountListResponse,
    AccountPlatformResponse,
    AccountTestResponse,
    BilibiliOAuthCallbackResponse,
    BilibiliOAuthStartResponse,
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

        record = ConnectedAccountRecord(
            platform="wechat",
            display_name=request.display_name or "微信公众号",
            status="connected",
            auth_type="app_secret",
            external_user_id=request.app_id,
            encrypted_credentials=self.cipher.encrypt_json(
                {
                    "app_id": request.app_id,
                    "app_secret": request.app_secret,
                    "access_token": token_payload.get("access_token"),
                }
            ),
            credential_metadata={"token_tested": request.test_connection},
            token_expires_at=token_expires_at,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self._to_response(get_adapter("wechat"), record)

    def start_bilibili_oauth(self) -> BilibiliOAuthStartResponse:
        state = self.cipher.make_state(
            {
                "platform": "bilibili",
                "nonce": uuid4().hex,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        authorize_url = BilibiliOpenPlatformClient().build_authorize_url(state)
        return BilibiliOAuthStartResponse(authorize_url=authorize_url, state=state)

    async def handle_bilibili_callback(
        self,
        code: str,
        state: str,
    ) -> BilibiliOAuthCallbackResponse:
        if self.session is None:
            raise RuntimeError("AccountService.handle_bilibili_callback requires a database session.")
        state_payload = self.cipher.read_state(state)
        if state_payload.get("platform") != "bilibili":
            raise PlatformClientError(
                "Invalid Bilibili OAuth state.",
                platform_code="INVALID_STATE",
                next_action="请从账号页面重新发起 B站授权。",
            )

        token_payload = await BilibiliOpenPlatformClient().exchange_code(code)
        data = token_payload.get("data", token_payload)
        expires_in = int(data.get("expires_in", token_payload.get("expires_in", 0)) or 0)
        token_expires_at = (
            datetime.now(UTC) + timedelta(seconds=max(expires_in - 300, 60))
            if expires_in
            else None
        )
        record = ConnectedAccountRecord(
            platform="bilibili",
            display_name=data.get("uname") or data.get("name") or "B站账号",
            status="connected",
            auth_type="oauth2",
            external_user_id=str(data.get("mid") or data.get("user_id") or ""),
            encrypted_credentials=self.cipher.encrypt_json(
                {
                    "access_token": data.get("access_token", token_payload.get("access_token")),
                    "refresh_token": data.get("refresh_token", token_payload.get("refresh_token")),
                    "scope": data.get("scope", token_payload.get("scope")),
                }
            ),
            credential_metadata={"scope": data.get("scope", token_payload.get("scope"))},
            token_expires_at=token_expires_at,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        safe_payload = self._redact_token_payload(token_payload)
        return BilibiliOAuthCallbackResponse(
            account=self._to_response(get_adapter("bilibili"), record),
            raw_response=safe_payload,
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
                details = {
                    "access_token_present": bool(credentials.get("access_token")),
                    "expires_at": record.token_expires_at.isoformat() if record.token_expires_at else None,
                }
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
                details=getattr(exc, "details", {}),
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
                else "账号尚未连接，真实发布前需要完成授权。"
            ),
        )

    @staticmethod
    def _redact_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
        redacted = dict(payload)
        for key in ("access_token", "refresh_token", "app_secret"):
            if key in redacted and redacted[key]:
                redacted[key] = "***"
        if isinstance(redacted.get("data"), dict):
            redacted["data"] = AccountService._redact_token_payload(redacted["data"])
        return redacted
