from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.content import PlatformLiteral


AccountStatusLiteral = Literal["not_configured", "connected", "expired", "error"]


class AccountPlatformResponse(BaseModel):
    account_id: str | None = Field(default=None, description="已连接账号 ID。未连接时为空。")
    platform: PlatformLiteral = Field(description="平台标识。")
    display_name: str = Field(description="平台展示名称。")
    status: AccountStatusLiteral = Field(description="账号连接状态。")
    auth_type: str = Field(description="授权方式。")
    real_publish_supported: bool = Field(description="当前后端是否已经支持该平台真实发布。")
    required_for_real_publish: bool = Field(description="真实发布是否需要账号授权。")
    capabilities: dict[str, Any] = Field(description="平台适配器声明的能力信息。")
    external_user_id: str | None = Field(default=None, description="平台外部用户 ID。")
    token_expires_at: datetime | None = Field(default=None, description="token 过期时间。")
    message: str = Field(description="面向前端展示的账号状态说明。")


class AccountListResponse(BaseModel):
    accounts: list[AccountPlatformResponse] = Field(description="当前平台账号占位状态列表。")


class WechatConnectRequest(BaseModel):
    app_id: str = Field(description="微信公众号 AppID。")
    app_secret: str = Field(description="微信公众号 AppSecret。")
    display_name: str | None = Field(default=None, description="前端展示用账号名称。")
    test_connection: bool = Field(default=True, description="保存前是否尝试获取 access_token。")


class BilibiliOAuthStartResponse(BaseModel):
    authorize_url: str = Field(description="前端需要跳转的 B站 OAuth 授权地址。")
    state: str = Field(description="后端生成的 OAuth state。")


class BilibiliOAuthCallbackResponse(BaseModel):
    account: AccountPlatformResponse = Field(description="授权成功后保存的账号信息。")
    raw_response: dict[str, Any] = Field(description="B站 token 接口返回的脱敏响应。")


class AccountTestResponse(BaseModel):
    account: AccountPlatformResponse = Field(description="被测试的账号信息。")
    ok: bool = Field(description="连接测试是否通过。")
    message: str = Field(description="连接测试结果说明。")
    details: dict[str, Any] = Field(default_factory=dict, description="平台返回的测试详情。")
