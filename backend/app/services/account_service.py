from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.registry import get_adapter, list_adapters
from backend.app.schemas.account import AccountListResponse, AccountPlatformResponse


class AccountService:
    def list_accounts(self) -> AccountListResponse:
        return AccountListResponse(
            accounts=[
                self._to_response(adapter)
                for adapter in list_adapters().values()
            ]
        )

    def get_account(self, platform: str) -> AccountPlatformResponse:
        return self._to_response(get_adapter(platform))

    @staticmethod
    def _to_response(adapter: PlatformAdapter) -> AccountPlatformResponse:
        capabilities = adapter.capabilities()
        auth = capabilities.get("auth", {})
        publish_modes = capabilities.get("publish_modes", [])
        real_publish_supported = any(mode in publish_modes for mode in ("draft", "publish"))

        return AccountPlatformResponse(
            platform=adapter.platform,
            display_name=adapter.display_name,
            status="not_configured",
            auth_type=auth.get("type", "unknown"),
            real_publish_supported=real_publish_supported,
            required_for_real_publish=auth.get("required_for_real_publish", True),
            capabilities=capabilities,
            message="第一阶段仅预留账号状态接口，暂不接入真实授权、账号校验或真实发布。",
        )
