"""initial second phase schema

Revision ID: 20260530_0001
Revises: 
Create Date: 2026-05-30 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260530_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "previews" not in tables:
        op.create_table(
            "previews",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("content_type", sa.String(length=32), nullable=False),
            sa.Column("raw_input", sa.JSON(), nullable=False),
            sa.Column("content_ir", sa.JSON(), nullable=False),
            sa.Column("drafts", sa.JSON(), nullable=False),
            sa.Column("validation_report", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "connected_accounts" not in tables:
        op.create_table(
            "connected_accounts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column("display_name", sa.String(length=160), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("auth_type", sa.String(length=64), nullable=False),
            sa.Column("external_user_id", sa.String(length=160), nullable=True),
            sa.Column("encrypted_credentials", sa.Text(), nullable=False),
            sa.Column("credential_metadata", sa.JSON(), nullable=False),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_connected_accounts_platform", "connected_accounts", ["platform"], unique=False)

    if "content_assets" not in tables:
        op.create_table(
            "content_assets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("asset_type", sa.String(length=32), nullable=False),
            sa.Column("purpose", sa.String(length=64), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("asset_metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_content_assets_asset_type", "content_assets", ["asset_type"], unique=False)
        op.create_index("ix_content_assets_sha256", "content_assets", ["sha256"], unique=False)

    if "publish_tasks" not in tables:
        op.create_table(
            "publish_tasks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("preview_id", sa.String(length=36), nullable=False),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("platforms", sa.JSON(), nullable=False),
            sa.Column("account_ids", sa.JSON(), nullable=False),
            sa.Column("asset_ids", sa.JSON(), nullable=False),
            sa.Column("platform_options", sa.JSON(), nullable=False),
            sa.Column("results", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["preview_id"], ["previews.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_publish_tasks_preview_id", "publish_tasks", ["preview_id"], unique=False)
    else:
        columns = {column["name"] for column in inspector.get_columns("publish_tasks")}
        if "account_ids" not in columns:
            op.add_column(
                "publish_tasks",
                sa.Column("account_ids", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            )
            op.alter_column("publish_tasks", "account_ids", server_default=None)
        if "asset_ids" not in columns:
            op.add_column(
                "publish_tasks",
                sa.Column("asset_ids", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            )
            op.alter_column("publish_tasks", "asset_ids", server_default=None)
        if "platform_options" not in columns:
            op.add_column(
                "publish_tasks",
                sa.Column("platform_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            )
            op.alter_column("publish_tasks", "platform_options", server_default=None)

    tables = set(sa.inspect(bind).get_table_names())
    if "publication_records" not in tables:
        op.create_table(
            "publication_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("task_id", sa.String(length=36), nullable=False),
            sa.Column("preview_id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=36), nullable=True),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=True),
            sa.Column("external_url", sa.Text(), nullable=True),
            sa.Column("external_status", sa.String(length=120), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("response_payload", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["connected_accounts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["preview_id"], ["previews.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["publish_tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_publication_records_account_id", "publication_records", ["account_id"], unique=False)
        op.create_index("ix_publication_records_platform", "publication_records", ["platform"], unique=False)
        op.create_index("ix_publication_records_preview_id", "publication_records", ["preview_id"], unique=False)
        op.create_index("ix_publication_records_task_id", "publication_records", ["task_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "publication_records" in tables:
        op.drop_table("publication_records")
    if "content_assets" in tables:
        op.drop_table("content_assets")
    if "connected_accounts" in tables:
        op.drop_table("connected_accounts")
    if "publish_tasks" in tables:
        columns = {column["name"] for column in sa.inspect(bind).get_columns("publish_tasks")}
        for column in ("platform_options", "asset_ids", "account_ids"):
            if column in columns:
                op.drop_column("publish_tasks", column)
