"""
One-time DB fix script — run inside the FastAPI container:

    docker exec -it tradie_dev_fastapi python scripts/apply_db_fixes.py

What it does (all idempotent — safe to run multiple times):
  1. Creates the job_events table if it doesn't exist yet.
  2. Moves any "open" job that already has leads distributed to "quoted",
     so the homeowner accept flow works correctly.
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
    print("ERROR: DATABASE_URL is not set.")
    sys.exit(1)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine  = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# asyncpg cannot execute multiple statements in one call — split them up.
CREATE_JOB_EVENTS_STEPS = [
    """
    CREATE TABLE IF NOT EXISTS job_events (
        id          BIGSERIAL    PRIMARY KEY,
        job_id      VARCHAR      NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        actor_id    VARCHAR      NOT NULL,
        actor_role  VARCHAR(30)  NOT NULL,
        action      VARCHAR(50)  NOT NULL,
        old_value   JSON         DEFAULT NULL,
        new_value   JSON         DEFAULT NULL,
        note        TEXT         DEFAULT NULL,
        ip_address  VARCHAR(45)  DEFAULT NULL,
        created_at  TIMESTAMP    DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_job_events_job_id     ON job_events(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_events_created_at ON job_events(created_at)",
]

FIX_JOB_STATUSES = """
UPDATE jobs
SET    status = 'quoted'
WHERE  status = 'open'
AND    id IN (SELECT DISTINCT job_id FROM leads);
"""

COUNT_JOBS = """
SELECT
    COUNT(*) FILTER (WHERE status = 'quoted') AS quoted,
    COUNT(*) FILTER (WHERE status = 'open')   AS open,
    COUNT(*) FILTER (WHERE status = 'hired')  AS hired
FROM jobs
WHERE is_deleted = false;
"""


async def main():
    print("\n" + "="*55)
    print(" APPLY DB FIXES")
    print("="*55)

    async with Session() as db:
        # ── Step 1: job_events table ──────────────────────────────
        print("\n[1/2] Creating job_events table (if not exists)…")
        for stmt in CREATE_JOB_EVENTS_STEPS:
            await db.execute(text(stmt))
        await db.commit()
        print("  ✅  job_events table ready")

        # ── Step 2: fix open jobs that have leads ─────────────────
        print("\n[2/2] Moving open jobs with leads → quoted…")
        result = await db.execute(text(FIX_JOB_STATUSES))
        await db.commit()
        print(f"  ✅  {result.rowcount} job(s) updated to 'quoted'")

        # ── Summary ───────────────────────────────────────────────
        counts = (await db.execute(text(COUNT_JOBS))).mappings().fetchone()
        print("\n  Job status summary:")
        print(f"    open   : {counts['open']}")
        print(f"    quoted : {counts['quoted']}")
        print(f"    hired  : {counts['hired']}")

    await engine.dispose()
    print("\n  ✅  All done — restart the FastAPI container to pick up code changes.\n")


asyncio.run(main())
