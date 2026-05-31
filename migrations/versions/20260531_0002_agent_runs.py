"""add agent run records

Revision ID: 20260531_0002
Revises: 20260530_0001
Create Date: 2026-05-31 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260531_0002"
down_revision: Union[str, None] = "20260530_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_runs" in tables:
        return

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workflow", sa.String(length=64), nullable=False),
        sa.Column("preview_id", sa.String(length=36), nullable=True),
        sa.Column("platforms", sa.JSON(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_preview_id", "agent_runs", ["preview_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "agent_runs" in tables:
        op.drop_index("ix_agent_runs_preview_id", table_name="agent_runs")
        op.drop_table("agent_runs")
