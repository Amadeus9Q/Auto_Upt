"""Delete all preview records from the database."""
import asyncio
from sqlalchemy import text
from backend.app.db.session import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT count(*) FROM previews"))
        count = result.scalar()
        print(f"previews count: {count}")

        result = await session.execute(text("DELETE FROM previews"))
        await session.commit()
        print(f"deleted {result.rowcount} preview rows")


if __name__ == "__main__":
    asyncio.run(main())
