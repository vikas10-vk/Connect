"""One-off script to delete orphan accounts."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

EMAILS = ["madness.hack1000@gmail.com", "ydivatagi@gmail.com"]
DB_URL = "postgresql+asyncpg://hipages:devpassword@localhost:5433/ProConnect_dev"


async def main():
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM users WHERE email = ANY(:emails) RETURNING email"),
            {"emails": EMAILS},
        )
        deleted = [r[0] for r in result.fetchall()]
        if deleted:
            print(f"Deleted {len(deleted)} row(s): {deleted}")
        else:
            print("No matching rows found (already deleted or never existed).")


asyncio.run(main())
