"""drop publication preview foreign key

Revision ID: 20260531_0003
Revises: 0c231f9ebaea
Create Date: 2026-05-31 06:20:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260531_0003"
down_revision: Union[str, None] = "0c231f9ebaea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "publication_records" not in inspector.get_table_names():
        return

    for foreign_key in inspector.get_foreign_keys("publication_records"):
        if foreign_key.get("constrained_columns") != ["preview_id"]:
            continue
        if foreign_key.get("referred_table") != "previews":
            continue

        constraint_name = foreign_key.get("name")
        if constraint_name:
            op.drop_constraint(constraint_name, "publication_records", type_="foreignkey")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "publication_records" not in inspector.get_table_names():
        return

    existing = [
        foreign_key
        for foreign_key in inspector.get_foreign_keys("publication_records")
        if foreign_key.get("constrained_columns") == ["preview_id"]
        and foreign_key.get("referred_table") == "previews"
    ]
    if existing:
        return

    op.create_foreign_key(
        op.f("publication_records_preview_id_fkey"),
        "publication_records",
        "previews",
        ["preview_id"],
        ["id"],
        ondelete="CASCADE",
    )
