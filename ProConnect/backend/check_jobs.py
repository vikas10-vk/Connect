import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def run():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    sf = async_sessionmaker(engine, class_=AsyncSession)
    async with sf() as db:
        r = await db.execute(text("""
            SELECT j.id, j.title, c.name, c.slug,
                (SELECT COUNT(*) FROM tradie_categories tc WHERE tc.category_id = c.id) as tc_count,
                (SELECT COUNT(*) FROM leads l WHERE l.job_id = j.id) as lead_count
            FROM jobs j LEFT JOIN categories c ON c.id = j.category_id
            ORDER BY j.created_at DESC LIMIT 10
        """))
        print("id | title | category | slug | tradies_in_cat | leads")
        print("-" * 80)
        for row in r.all():
            print(f"{row[0][:8]}... | {(row[1] or '')[:30]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}")
    await engine.dispose()

asyncio.run(run())
