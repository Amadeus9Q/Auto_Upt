from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.content import PlatformLiteral


AccountStatusLiteral = Literal["not_configured", "connected", "expired"]


class AccountPlatformResponse(BaseModel):
    platform: PlatformLiteral = Field(description="平台标识。")
    display_name: str = Field(description="平台展示名称。")
    status: AccountStatusLiteral = Field(description="账号连接状态。第一阶段默认 not_configured。")
    auth_type: str = Field(description="后续真实发布可能采用的授权方式。")
    real_publish_supported: bool = Field(description="当前后端是否已经支持该平台真实发布。")
    required_for_real_publish: bool = Field(description="真实发布是否需要账号授权。")
    capabilities: dict[str, Any] = Field(description="平台适配器声明的能力信息。")
    message: str = Field(description="面向前端展示的账号状态说明。")


class AccountListResponse(BaseModel):
    accounts: list[AccountPlatformResponse] = Field(description="当前平台账号占位状态列表。")
