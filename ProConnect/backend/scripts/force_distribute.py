"""
Force re-distribute leads for a specific job — run from the backend/ directory:

    python scripts/force_distribute.py <job_id>

Example:
    python scripts/force_distribute.py abc123-job-id

What it does:
  1. Clears match_intelligence on the job (removes the idempotency guard so
     _distribute_leads won't skip it as "already processed").
  2. Runs the full lead distribution logic in-process (no Celery required).
  3. Prints exactly which tradies were matched and why.

Use this after fixing a category mismatch, adding a tradie, or any other
condition that previously blocked distribution.
"""

import asyncio
import os
import sys
from pathlib import Path

# ── Ensure the backend root (parent of scripts/) is on sys.path ──────────────
# This lets us import `tasks.lead_tasks`, `models.*`, `services.*` etc.
# Works both locally (ProConnect/backend/) and inside Docker (/app/).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ── Load .env so DATABASE_URL etc. are available ─────────────────────────────
# Walk up from script location until a .env file is found (works locally and in Docker).
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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set. Make sure your .env file exists and contains DATABASE_URL.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python scripts/force_distribute.py <job_id>")
    print("       python scripts/force_distribute.py all-recent   (re-runs last 5 jobs)")
    sys.exit(1)

JOB_ARG = sys.argv[1]

engine  = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def force_one(job_id: str):
    async with Session() as db:
        # Verify job exists
        result = await db.execute(
            text("SELECT id, title, match_intelligence FROM jobs WHERE id = :jid"),
            {"jid": job_id}
        )
        job_row = result.mappings().fetchone()
        if not job_row:
            print(f"  ❌  Job not found: {job_id}")
            return False

        print(f"\n  Job: {job_row['title']} (id={job_id})")

        if job_row['match_intelligence']:
            print("  ℹ️   Clearing match_intelligence (idempotency guard) so distribution will re-run…")
            await db.execute(
                text("UPDATE jobs SET match_intelligence = NULL WHERE id = :jid"),
                {"jid": job_id}
            )
            await db.commit()
            print("  ✅  match_intelligence cleared")
        else:
            print("  ℹ️   match_intelligence was already NULL — distribution never ran or was cleared")

    # Now run distribution using the same async logic as the Celery task
    print(f"\n  Running lead distribution for {job_id}…\n")
    try:
        # Build a fresh engine + session factory for the task (mirrors what Celery does)
        from sqlalchemy.ext.asyncio import (
            AsyncSession as _AsyncSession,
        )
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker as _async_sessionmaker,
        )
        from sqlalchemy.ext.asyncio import (
            create_async_engine as _create_engine,
        )
        task_engine = _create_engine(DATABASE_URL, pool_size=2, max_overflow=0, pool_pre_ping=True)
        task_session = _async_sessionmaker(task_engine, class_=_AsyncSession, expire_on_commit=False)

        from tasks.lead_tasks import _distribute_leads
        await _distribute_leads(job_id, task_session)
        await task_engine.dispose()
        return True
    except Exception as e:
        print(f"  ❌  Distribution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print(f"\n{'='*60}")
    print(" FORCE DISTRIBUTE LEADS")
    print(f"{'='*60}")

    if JOB_ARG == "all-recent":
        # Re-run for the 5 most recent jobs
        async with Session() as db:
            result = await db.execute(
                text("SELECT id, title FROM jobs ORDER BY created_at DESC LIMIT 5")
            )
            jobs = result.mappings().fetchall()

        if not jobs:
            print("\n  ❌  No jobs found in database")
        else:
            print(f"\n  Found {len(jobs)} recent job(s):\n")
            for j in jobs:
                print(f"    • {j['title']} ({j['id']})")
            print()
            for j in jobs:
                await force_one(j['id'])
    else:
        success = await force_one(JOB_ARG)
        if success:
            print("\n  ✅  Done — check the output above for which tradies were matched.")
            print("      The tradie should now see the lead in their dashboard.\n")
        else:
            print("\n  ❌  Distribution did not complete. Fix the issues above and retry.\n")

    await engine.dispose()


asyncio.run(main())
