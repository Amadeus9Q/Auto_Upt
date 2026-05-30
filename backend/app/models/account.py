from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class ConnectedAccountRecord(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    platform: Mapped[str] = mapped_column(String(32), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="connected")
    auth_type: Mapped[str] = mapped_column(String(64))
    external_user_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    credential_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
