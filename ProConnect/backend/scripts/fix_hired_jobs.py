"""
One-time fix: jobs with an accepted quote should be "hired".

    docker exec -it tradie_dev_fastapi python scripts/fix_hired_jobs.py
"""
import asyncio
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

def _load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for parent in [_BACKEND_ROOT, *_BACKEND_ROOT.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=True)
            return
_load_env()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine  = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with Session() as db:
        # Move jobs with accepted quotes to "hired"
        result = await db.execute(text("""
            UPDATE jobs
            SET    status = 'hired',
                   updated_at = NOW()
            WHERE  status NOT IN ('hired','in_progress','completed','closed','cancelled')
            AND    id IN (
                SELECT DISTINCT j.id
                FROM   jobs j
                JOIN   leads l ON l.job_id = j.id
                JOIN   quotes q ON q.lead_id = l.id
                WHERE  q.status = 'accepted'
            )
        """))
        await db.commit()
        print(f"  ✅  {result.rowcount} job(s) set to 'hired'")

        # Summary
        rows = (await db.execute(text(
            "SELECT id, title, status FROM jobs WHERE is_deleted=false ORDER BY created_at DESC LIMIT 10"
        ))).mappings().fetchall()
        print("\nJob status summary:")
        for r in rows:
            print(f"  [{r['status']:12}] {r['title']}")

    await engine.dispose()

asyncio.run(main())
