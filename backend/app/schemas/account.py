from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.content import PlatformLiteral


AccountStatusLiteral = Literal["connected", "disconnected", "expired", "error"]


class AccountPlatformResponse(BaseModel):
    account_id: str | None = Field(default=None, description="已连接账号 ID。未连接时为空。")
    platform: PlatformLiteral = Field(description="平台标识。")
    display_name: str = Field(description="账号或平台展示名称。")
    status: AccountStatusLiteral = Field(description="账号连接状态。")
    auth_type: str = Field(description="授权方式，例如 app_secret、oauth、browser_assisted。")
    token_expires_at: str | None = Field(default=None, description="Token 过期时间；占位或未连接时为空。")
    updated_at: str | None = Field(default=None, description="账号状态更新时间。")
    real_publish_supported: bool = Field(default=False, description="当前后端是否支持该平台真实发布。")
    required_for_real_publish: bool = Field(default=True, description="真实发布是否需要账号授权。")
    capabilities: dict[str, Any] = Field(default_factory=dict, description="平台适配器声明的能力信息。")
    message: str = Field(default="", description="面向前端展示的账号状态说明。")


class AccountListResponse(BaseModel):
    accounts: list[AccountPlatformResponse] = Field(description="当前平台账号状态列表。")


class WechatConnectRequest(BaseModel):
    app_id: str = Field(min_length=1, description="公众号 AppID。")
    app_secret: str = Field(min_length=1, description="公众号 AppSecret。")
    display_name: str | None = Field(default=None, description="前端展示的账号名称。")


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
    platform: PlatformLiteral = Field(description="平台标识。")
    ok: bool = Field(description="连接测试是否通过。")
    message: str = Field(description="连接测试结果说明。")
