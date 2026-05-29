from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PlatformLiteral = Literal["wechat", "zhihu", "xiaohongshu", "bilibili"]
ContentTypeLiteral = Literal["article", "video", "mixed"]
PublishModeLiteral = Literal["simulate", "draft", "publish"]
TaskStatusLiteral = Literal["pending", "running", "succeeded", "failed"]


class ContentAsset(BaseModel):
    asset_type: str = Field(
        default="image",
        description="素材类型，例如 image、video、file。",
    )
    url: str | None = Field(
        default=None,
        description="素材访问地址，可以是远程 URL 或后续扩展的本地资源地址。",
    )
    description: str | None = Field(
        default=None,
        description="素材说明，例如封面图、正文配图、视频文件等。",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="素材扩展信息，例如尺寸、比例、大小、来源等。",
    )


class ContentInput(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=160,
        description="内容标题。为空时后端会尝试从正文首个非空行生成标题。",
    )
    body: str = Field(
        min_length=1,
        description="原始正文内容，支持 Markdown、普通文本或后续扩展的富文本转换结果。",
    )
    content_type: ContentTypeLiteral = Field(
        default="article",
        description="内容类型。article 表示文章，video 表示视频内容，mixed 表示图文/视频混合内容。",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="原始标签列表。后端会去重并去掉标签前缀 #。",
    )
    assets: list[ContentAsset] = Field(
        default_factory=list,
        description="内容关联素材列表，例如封面图、正文图片或视频资源。",
    )


class AdaptContentRequest(ContentInput):
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要适配的平台列表。为空时默认适配全部已支持平台。",
    )


class PreviewCreateRequest(ContentInput):
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要生成预览的平台列表。为空时默认生成全部已支持平台预览。",
    )


class PublishTaskCreateRequest(BaseModel):
    preview_id: str = Field(description="预览记录 ID。必须来自 POST /api/v1/previews 的返回值。")
    mode: PublishModeLiteral = Field(
        default="simulate",
        description="发布模式。当前 MVP 仅支持 simulate，draft 和 publish 会返回 400。",
    )
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要模拟发布的平台列表。为空时使用该预览记录中已有的全部平台草稿。",
    )


class NormalizeResponse(BaseModel):
    content_ir: dict[str, Any] = Field(
        description="统一内容 IR，包含标题、正文、摘要、标签、素材、字数和创建时间等信息。",
    )


class AdaptContentResponse(BaseModel):
    content_ir: dict[str, Any] = Field(description="统一内容 IR。")
    drafts: dict[str, dict[str, Any]] = Field(
        description="按平台分组的草稿内容。key 为平台名，value 为对应平台草稿。",
    )
    validation_report: dict[str, list[dict[str, Any]]] = Field(
        description="按平台分组的校验结果。每条校验结果包含级别、编码、字段和说明。",
    )


class PreviewResponse(BaseModel):
    preview_id: str = Field(description="预览记录 ID，可用于查询预览详情或创建模拟发布任务。")
    content_ir: dict[str, Any] = Field(description="统一内容 IR。")
    drafts: dict[str, dict[str, Any]] = Field(description="按平台分组的草稿内容。")
    validation_report: dict[str, list[dict[str, Any]]] = Field(
        description="按平台分组的格式和素材校验结果。",
    )
    created_at: datetime | None = Field(default=None, description="预览记录创建时间。")


class PublishTaskResponse(BaseModel):
    task_id: str = Field(description="发布任务 ID。")
    preview_id: str = Field(description="该发布任务关联的预览记录 ID。")
    mode: PublishModeLiteral = Field(description="发布模式。当前 MVP 只会成功执行 simulate。")
    status: TaskStatusLiteral = Field(description="任务状态，例如 succeeded 或 failed。")
    platforms: list[str] = Field(description="本次任务覆盖的平台列表。")
    results: dict[str, Any] = Field(
        description="按平台分组的模拟发布结果，包含预览 URL、截图占位路径和状态信息。",
    )
    error_message: str | None = Field(default=None, description="任务级错误信息。成功时为空。")
    created_at: datetime | None = Field(default=None, description="任务创建时间。")
    updated_at: datetime | None = Field(default=None, description="任务最后更新时间。")


class PlatformListResponse(BaseModel):
    platforms: list[PlatformLiteral] = Field(description="当前后端支持的平台列表。")
