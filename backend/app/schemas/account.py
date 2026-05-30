from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class BilibiliCaptchaResponse(BaseModel):
    gt: str = Field(description="Geetest captcha gt 参数，前端初始化极验组件使用。")
    challenge: str = Field(description="Geetest challenge，前端初始化极验组件使用。")
    token: str = Field(description="B站 captcha token，登录时回传。")


class BilibiliLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(description="B站登录用户名（手机号或邮箱）。")
    password: str = Field(description="B站登录密码。")
    token: str = Field(description="captcha 接口返回的 token。")
    challenge: str = Field(description="Geetest challenge 值。")
    geetest_validate: str = Field(alias="validate", description="Geetest 验证结果 validate。")
    seccode: str = Field(description="Geetest seccode，通常为 validate 加后缀。")
    display_name: str | None = Field(default=None, description="前端展示用账号名称。")


class BilibiliLoginResponse(BaseModel):
    account: AccountPlatformResponse = Field(description="登录成功后保存的账号信息。")
    message: str = Field(description="登录结果说明。")


class AccountTestResponse(BaseModel):
    account: AccountPlatformResponse = Field(description="被测试的账号信息。")
    ok: bool = Field(description="连接测试是否通过。")
    message: str = Field(description="连接测试结果说明。")
    details: dict[str, Any] = Field(default_factory=dict, description="平台返回的测试详情。")
