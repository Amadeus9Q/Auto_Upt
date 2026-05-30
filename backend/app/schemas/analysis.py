"""内容分析相关 Schema —— 章节划分、子标题提取、媒体识别、平台文案生成。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


MediaKindLiteral = Literal["image", "video", "audio"]
ChapterLevelLiteral = Literal[1, 2, 3]


class MediaItem(BaseModel):
    """正文中识别到的单个媒体资源。"""
    asset_id: str | None = Field(default=None, description="关联素材 ID，来自前端上传或正文标记。")
    kind: MediaKindLiteral = Field(description="媒体类型：image / video / audio。")
    name: str | None = Field(default=None, description="文件名或描述。")
    src: str | None = Field(default=None, description="媒体资源地址或预览 URL。")
    mime_type: str | None = Field(default=None, description="MIME 类型。")
    role: Literal["inline", "cover", "main"] | None = Field(
        default="inline", description="媒体在正文中的角色：inline 内联 / cover 封面 / main 主体视频。"
    )
    position: int = Field(default=0, description="该媒体在正文中的大致位置索引（基于段落顺序）。")
    surrounding_text: str | None = Field(
        default=None, description="媒体前后的上下文文本片段，用于后续 AI 改写。"
    )


class Chapter(BaseModel):
    """正文章节信息。"""
    level: int = Field(description="标题层级，1 = h1 / #, 2 = h2 / ##, 3 = h3 / ###。")
    title: str = Field(description="章节标题（去除 markdown 标记的纯文本）。")
    content: str = Field(description="该章节下的正文内容（不含子章节标题）。")
    start_index: int = Field(default=0, description="章节在原文中的起始位置索引。")
    word_count: int = Field(default=0, description="该章节字数。")
    media_items: list[MediaItem] = Field(
        default_factory=list, description="该章节内识别到的媒体资源。"
    )
    sub_chapters: list["Chapter"] = Field(
        default_factory=list, description="子章节列表（h2 下嵌套的 h3）。"
    )


class ContentAnalysis(BaseModel):
    """内容分析完整结果。"""
    title: str | None = Field(default=None, description="识别到的标题。")
    subtitle: str | None = Field(default=None, description="识别到的副标题或导语。")
    chapters: list[Chapter] = Field(default_factory=list, description="一级章节列表（h1 / #）。")
    flat_chapters: list[Chapter] = Field(
        default_factory=list, description="扁平化后的所有章节（含嵌套），便于遍历。"
    )
    all_media: list[MediaItem] = Field(default_factory=list, description="正文中所有识别到的媒体资源。")
    media_by_kind: dict[str, list[MediaItem]] = Field(
        default_factory=dict, description="按类型分组的媒体资源：{image: [...], video: [...], audio: [...]}。"
    )
    summary: str = Field(default="", description="正文摘要。")
    total_word_count: int = Field(default=0, description="正文总字数。")
    tags: list[str] = Field(default_factory=list, description="归一化后的标签。")
    content_type: str = Field(default="article", description="内容类型：article/video/mixed。")


class PlatformCopy(BaseModel):
    """单个平台生成的文案。"""
    platform: str = Field(description="平台标识：wechat / zhihu / xiaohongshu / bilibili。")
    display_name: str = Field(description="平台展示名。")
    title: str = Field(description="平台适配后的标题。")
    subtitle: str | None = Field(default=None, description="副标题/导语。")
    sections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="按章节划分的结构化内容：[{heading, paragraphs, media_hints, platform_hints}]。",
    )
    plain_body: str = Field(description="平台适配后的纯文本正文。")
    tags: list[str] = Field(default_factory=list, description="平台适配后的标签。")
    media_recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="媒体使用建议：[{asset_id, kind, action: keep/replace/skip, reason}]。",
    )
    style_notes: list[str] = Field(default_factory=list, description="平台风格提示。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据。")


class AgentAnalysisResponse(BaseModel):
    """Agent 分析完整响应。"""
    analysis: ContentAnalysis = Field(description="内容分析结果。")
    platform_copies: dict[str, PlatformCopy] = Field(
        default_factory=dict, description="按平台分组的文案。"
    )
