from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PublicationResponse(BaseModel):
    publication_id: str = Field(description="发布记录 ID。")
    task_id: str = Field(description="关联发布任务 ID。")
    preview_id: str = Field(description="关联预览 ID。")
    account_id: str | None = Field(default=None, description="关联账号 ID。")
    platform: str = Field(description="平台标识。")
    mode: str = Field(description="发布模式。")
    status: str = Field(description="内部发布状态。")
    external_id: str | None = Field(default=None, description="平台外部发布 ID。")
    external_url: str | None = Field(default=None, description="平台外部 URL。")
    external_status: str | None = Field(default=None, description="平台外部状态。")
    response_payload: dict[str, Any] = Field(description="平台响应快照。")
    error_message: str | None = Field(default=None, description="错误信息。")
    created_at: datetime | None = Field(default=None, description="创建时间。")
    updated_at: datetime | None = Field(default=None, description="更新时间。")


class PublicationDeleteResponse(BaseModel):
    publication_id: str = Field(description="发布记录 ID。")
    platform: str = Field(description="平台标识。")
    status: str = Field(description="删除后的内部状态。")
    message: str = Field(description="删除结果说明。")
    details: dict[str, Any] = Field(default_factory=dict, description="平台响应详情。")
