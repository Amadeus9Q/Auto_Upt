from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.sql_echo)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from backend.app.models import account, asset, content, platform, publication  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_publish_schema)


def _json_column_sql(dialect_name: str, nullable: bool = False) -> str:
    null_sql = "" if nullable else " NOT NULL"
    if dialect_name == "postgresql":
        return f"JSONB{null_sql} DEFAULT '{{}}'::jsonb"
    return f"JSON{null_sql} DEFAULT '{{}}'"


def _add_missing_columns(conn, table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    dialect_name = conn.dialect.name
    for column_name, column_sql in columns.items():
        if column_name in existing_columns:
            continue

        if dialect_name == "postgresql":
            statement = f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{column_name}" {column_sql}'
        else:
            statement = f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}'
        conn.execute(text(statement))


def _ensure_publish_schema(conn) -> None:
    json_required = _json_column_sql(conn.dialect.name)
    _add_missing_columns(
        conn,
        "publish_tasks",
        {
            "account_ids": json_required,
            "asset_ids": json_required,
            "platform_options": json_required,
        },
    )
    _add_missing_columns(
        conn,
        "publication_records",
        {
            "external_url": "TEXT",
            "external_status": "VARCHAR(120)",
            "request_payload": json_required,
            "response_payload": json_required,
            "error_message": "TEXT",
        },
    )


async def close_db() -> None:
    await engine.dispose()
