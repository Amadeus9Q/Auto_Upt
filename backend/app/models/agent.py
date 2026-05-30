from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    status: Mapped[str] = mapped_column(String(32), default="succeeded")
    workflow: Mapped[str] = mapped_column(String(64), default="adapt_preview")
    preview_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_calls: Mapped[list[dict]] = mapped_column(JSON, default=list)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
