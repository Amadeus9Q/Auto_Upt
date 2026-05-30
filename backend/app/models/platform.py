from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class PlatformName(StrEnum):
    WECHAT = "wechat"
    ZHIHU = "zhihu"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"


class PublishMode(StrEnum):
    SIMULATE = "simulate"
    DRAFT = "draft"
    PUBLISH = "publish"


class PublishTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PublishTaskRecord(Base):
    __tablename__ = "publish_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    preview_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(32), default=PublishMode.SIMULATE)
    status: Mapped[str] = mapped_column(
        String(32),
        default=PublishTaskStatus.PENDING,
    )
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    account_ids: Mapped[dict] = mapped_column(JSON, default=dict)
    asset_ids: Mapped[dict] = mapped_column(JSON, default=dict)
    platform_options: Mapped[dict] = mapped_column(JSON, default=dict)
    drafts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    content_ir: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
