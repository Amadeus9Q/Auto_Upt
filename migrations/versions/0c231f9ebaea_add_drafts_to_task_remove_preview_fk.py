"""add_drafts_to_task_remove_preview_fk

Revision ID: 0c231f9ebaea
Revises: 20260531_0002
Create Date: 2026-05-31 04:44:17.708066
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0c231f9ebaea'
down_revision: Union[str, None] = '20260531_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("publish_tasks")}

    if "drafts" not in columns:
        op.add_column("publish_tasks", sa.Column("drafts", sa.JSON(), nullable=True))
    if "content_ir" not in columns:
        op.add_column("publish_tasks", sa.Column("content_ir", sa.JSON(), nullable=True))
    if "drafts" not in columns or "content_ir" not in columns:
        # Only try to drop constraint if we're truly altering the table
        pass

    # Drop preview FK
    constraints = {c["name"] for c in inspector.get_foreign_keys("publish_tasks")}
    fk_name = op.f("publish_tasks_preview_id_fkey")
    actual_fk = None
    for c in inspector.get_foreign_keys("publish_tasks"):
        if "preview_id" in c.get("constrained_columns", []):
            actual_fk = c["name"]
            break
    if actual_fk:
        op.drop_constraint(actual_fk, "publish_tasks", type_="foreignkey")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("publish_tasks")}

    # Re-add FK if it doesn't exist
    constraints = [c["name"] for c in inspector.get_foreign_keys("publish_tasks")]
    fk_name = op.f("publish_tasks_preview_id_fkey")
    if fk_name not in constraints:
        op.create_foreign_key(fk_name, "publish_tasks", "previews", ["preview_id"], ["id"], ondelete="CASCADE")

    if "content_ir" in columns:
        op.drop_column("publish_tasks", "content_ir")
    if "drafts" in columns:
        op.drop_column("publish_tasks", "drafts")
