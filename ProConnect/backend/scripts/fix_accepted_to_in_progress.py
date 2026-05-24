"""
One-time fix: jobs that have an accepted quote but are NOT yet in_progress.

Previously the accept flow wrote status='hired'; now it writes status='in_progress'
directly. This script brings any old/stuck records in line with the new flow.

    docker exec -it tradie_dev_fastapi python scripts/fix_accepted_to_in_progress.py
"""
import asyncio, os, sys
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
    print("ERROR: DATABASE_URL not set"); sys.exit(1)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

engine  = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with Session() as db:
        # Move any job that has an accepted quote but is still open/quoted/hired
        result = await db.execute(text("""
            UPDATE jobs
            SET    status = 'in_progress',
                   updated_at = NOW()
            WHERE  status NOT IN ('in_progress', 'completed', 'closed', 'cancelled')
            AND    id IN (
                SELECT DISTINCT j.id
                FROM   jobs j
                JOIN   leads l ON l.job_id = j.id
                JOIN   quotes q ON q.lead_id = l.id
                WHERE  q.status = 'accepted'
            )
        """))
        await db.commit()
        print(f"  ✅  {result.rowcount} job(s) moved to 'in_progress'")

        # Summary
        rows = (await db.execute(text(
            "SELECT id, title, status FROM jobs WHERE is_deleted=false ORDER BY created_at DESC LIMIT 10"
        ))).mappings().fetchall()
        print("\nJob status summary:")
        for r in rows:
            print(f"  [{r['status']:14}] {r['title']}")

    await engine.dispose()

asyncio.run(main())
