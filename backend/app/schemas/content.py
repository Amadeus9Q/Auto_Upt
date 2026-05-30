from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PlatformLiteral = Literal["wechat", "zhihu", "xiaohongshu", "bilibili"]
ContentTypeLiteral = Literal["article", "video", "mixed"]
PublishModeLiteral = Literal["simulate", "draft", "publish"]
TaskStatusLiteral = Literal["pending", "running", "succeeded", "failed"]


class ContentAsset(BaseModel):
    id: str | None = Field(default=None, description="前端生成的素材稳定 ID，用于正文块引用。")
    name: str | None = Field(default=None, description="前端选择的本地素材文件名。")
    type: str | None = Field(default=None, description="前端素材类型，例如 image、video、audio、cover。")
    size: int | None = Field(default=None, description="前端素材文件大小，单位为字节。")
    mime_type: str | None = Field(default=None, description="前端素材 MIME 类型。")
    usage: str | None = Field(default=None, description="前端素材用途，例如 default_cover、body_image、bilibili_video。")
    preview_url: str | None = Field(default=None, description="前端本地预览 URL，仅用于当前浏览器会话内的预览回显。")
    asset_type: str = Field(default="image", description="素材类型，例如 image、video、file。")
    url: str | None = Field(default=None, description="素材访问地址，可以是远程 URL 或后续扩展的本地资源地址。")
    description: str | None = Field(default=None, description="素材说明，例如封面图、正文配图、视频文件等。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="素材扩展信息。")


class ContentBlock(BaseModel):
    type: Literal["text", "asset"] = Field(description="正文块类型。")
    text: str | None = Field(default=None, description="文本块内容。")
    asset_id: str | None = Field(default=None, description="素材块引用的素材 ID。")
    asset_kind: Literal["image", "video", "audio"] | None = Field(default=None, description="素材块类型。")
    role: Literal["inline", "cover"] | None = Field(default="inline", description="素材在正文中的角色。")


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
    content_blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="结构化正文块，文本和素材引用按正文插入顺序排列。",
    )
    cover_asset_id: str | None = Field(
        default=None,
        description="封面图对应的素材 ID。为空时由平台 Adapter 按素材用途自动选择。",
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
        description="发布模式。当前支持 simulate；draft 和 publish 用于第二阶段前端联调，后端返回模拟结果。",
    )
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要发布的平台列表。为空时使用该预览记录中已有的全部平台草稿。",
    )


class NormalizeResponse(BaseModel):
    content_ir: dict[str, Any] = Field(
        description="统一内容 IR，包含标题、正文、摘要、标签、素材、正文块、字数和创建时间等信息。",
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
    preview_id: str = Field(description="预览记录 ID，可用于查询预览详情或创建发布任务。")
    content_ir: dict[str, Any] = Field(description="统一内容 IR。")
    drafts: dict[str, dict[str, Any]] = Field(description="按平台分组的草稿内容。")
    validation_report: dict[str, list[dict[str, Any]]] = Field(
        description="按平台分组的格式和素材校验结果。",
    )
    created_at: datetime | None = Field(default=None, description="预览记录创建时间。")


class PublishTaskResponse(BaseModel):
    task_id: str = Field(description="发布任务 ID。")
    preview_id: str = Field(description="该发布任务关联的预览记录 ID。")
    mode: PublishModeLiteral = Field(description="发布模式。")
    status: TaskStatusLiteral = Field(description="任务状态，例如 succeeded 或 failed。")
    platforms: list[str] = Field(description="本次任务覆盖的平台列表。")
    results: dict[str, Any] = Field(description="按平台分组的发布结果。")
    error_message: str | None = Field(default=None, description="任务级错误信息。成功时为空。")
    created_at: datetime | None = Field(default=None, description="任务创建时间。")
    updated_at: datetime | None = Field(default=None, description="任务最后更新时间。")


class PlatformListResponse(BaseModel):
    platforms: list[PlatformLiteral] = Field(description="当前后端支持的平台列表。")
