from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AssetTypeLiteral = Literal["image", "video", "file"]


class AssetResponse(BaseModel):
    asset_id: str = Field(description="素材 ID。")
    asset_type: str = Field(description="素材类型，例如 image、video、file。")
    purpose: str = Field(description="素材用途，例如 cover、body_image、video。")
    original_filename: str = Field(description="上传时的原始文件名。")
    filename: str = Field(description="后端存储文件名。")
    content_type: str = Field(description="MIME 类型。")
    file_size: int = Field(description="文件大小，单位字节。")
    sha256: str = Field(description="文件 SHA-256 摘要。")
    url: str = Field(description="本地开发可访问 URL。")
    metadata: dict[str, Any] = Field(description="素材扩展信息。")
    created_at: datetime | None = Field(default=None, description="素材创建时间。")


class AssetListResponse(BaseModel):
    assets: list[AssetResponse] = Field(description="素材列表。")
