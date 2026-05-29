from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class PreviewRecord(Base):
    __tablename__ = "previews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(32), default="article")
    raw_input: Mapped[dict] = mapped_column(JSON, default=dict)
    content_ir: Mapped[dict] = mapped_column(JSON, default=dict)
    drafts: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
