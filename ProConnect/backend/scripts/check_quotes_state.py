"""
Quick diagnostic — shows current quotes, leads and job statuses.

    docker exec -it tradie_dev_fastapi python scripts/check_quotes_state.py
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
        print("\n=== JOBS ===")
        rows = (await db.execute(text(
            "SELECT id, title, status FROM jobs WHERE is_deleted=false ORDER BY created_at DESC LIMIT 10"
        ))).mappings().fetchall()
        for r in rows:
            print(f"  [{r['status']:10}] {r['title'][:50]}  id={r['id'][:8]}…")

        print("\n=== LEADS ===")
        rows = (await db.execute(text(
            "SELECT l.id, l.status, l.tradie_id, j.title FROM leads l JOIN jobs j ON j.id=l.job_id ORDER BY l.id LIMIT 20"
        ))).mappings().fetchall()
        for r in rows:
            print(f"  [{r['status']:10}] job='{r['title'][:40]}' lead={r['id'][:8]}…")

        print("\n=== QUOTES ===")
        rows = (await db.execute(text(
            "SELECT q.id, q.status, q.amount, q.lead_id, j.title "
            "FROM quotes q JOIN leads l ON l.id=q.lead_id JOIN jobs j ON j.id=l.job_id "
            "ORDER BY q.created_at DESC LIMIT 10"
        ))).mappings().fetchall()
        if not rows:
            print("  ⚠️  NO QUOTES FOUND — tradie has not submitted a quote yet.")
            print("     → Log in as tradie → Leads tab → click 'Send Quote'")
        for r in rows:
            print(f"  [{r['status']:10}] ${r['amount']:.0f}  job='{r['title'][:40]}'  quote={r['id'][:8]}…")

    await engine.dispose()

asyncio.run(main())
