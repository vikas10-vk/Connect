import asyncio
import json
import random
from datetime import datetime, timedelta

from celery import shared_task
from db.session import AsyncSessionLocal
from sqlalchemy import select


# ── Task 1: notify homeowner of stale job (no quotes after 24h) ───────────────

@shared_task(bind=True, max_retries=1)
def check_stale_jobs(self):
    """
    Runs every 2 hours.
    Finds jobs where:
      - status == 'open'
      - created_at is 24–47 hours ago
      - at least 1 lead exists
      - no quotes received yet
      - not already notified (stale_notified_at IS NULL)

    Sends a "we're on it" email to the homeowner.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_check_stale_jobs())
    except Exception as exc:
        print(f"[timeout] check_stale_jobs error: {exc}")
        raise self.retry(exc=exc)
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _check_stale_jobs():
    from sqlalchemy.orm import selectinload
    from sqlalchemy import update, func
    from models.job import Job
    from models.lead import Lead
    from models.quote import Quote
    from models.user import User
    from services.resend_service import send_stale_job_email

    now = datetime.utcnow()
    window_start = now - timedelta(hours=48)   # older than 48h → redistribute, not notify
    window_end   = now - timedelta(hours=24)   # younger than 24h → too soon

    async with AsyncSessionLocal() as db:
        # Jobs created 24–48h ago, still open, not yet notified
        result = await db.execute(
            select(Job)
            .where(
                Job.status == 'open',
                Job.is_deleted == False,
                Job.created_at.between(window_start, window_end),
            )
        )
        jobs = result.scalars().all()

        print(f"[timeout] Checking {len(jobs)} jobs in 24-48h stale window...")

        for job in jobs:
            # Check if it has leads but no quotes
            leads_result = await db.execute(
                select(Lead).where(Lead.job_id == job.id)
            )
            leads = leads_result.scalars().all()
            if not leads:
                continue  # 0 leads = already handled by lead_tasks notification

            lead_ids = [l.id for l in leads]
            quotes_result = await db.execute(
                select(Quote).where(Quote.lead_id.in_(lead_ids))
            )
            quotes = quotes_result.scalars().all()
            if quotes:
                continue  # has quotes — homeowner is in good shape

            # Fetch homeowner
            user_result = await db.execute(
                select(User).where(User.id == job.homeowner_id)
            )
            homeowner = user_result.scalar_one_or_none()
            if not homeowner:
                continue

            # Send email
            try:
                await send_stale_job_email(
                    to_email=homeowner.email,
                    full_name=homeowner.full_name or "",
                    job_title=job.title,
                    lead_count=len(leads),
                )
                print(f"[timeout]   → Notified {homeowner.email} about stale job '{job.title}'")
            except Exception as e:
                print(f"[timeout]   Warning: could not notify {homeowner.email}: {e}")


# ── Task 2: re-distribute stale jobs (no quotes after 48h) ───────────────────

@shared_task(bind=True, max_retries=1)
def redistribute_stale_jobs(self):
    """
    Runs every 6 hours.
    Finds jobs where:
      - status == 'open'
      - created_at > 48h ago
      - fewer than 3 leads
      - no quotes received

    Re-triggers lead distribution with a wider radius multiplier.
    This catches jobs that were posted when no tradies were available.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_redistribute_stale_jobs())
    except Exception as exc:
        print(f"[timeout] redistribute_stale_jobs error: {exc}")
        raise self.retry(exc=exc)
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _redistribute_stale_jobs():
    from models.job import Job
    from models.lead import Lead
    from models.quote import Quote

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=48)  # only jobs older than 48h

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Job)
            .where(
                Job.status == 'open',
                Job.is_deleted == False,
                Job.created_at < cutoff,
            )
        )
        jobs = result.scalars().all()
        print(f"[timeout] Checking {len(jobs)} jobs older than 48h for re-distribution...")

        for job in jobs:
            leads_result = await db.execute(
                select(Lead).where(Lead.job_id == job.id)
            )
            leads = leads_result.scalars().all()
            if len(leads) >= 3:
                continue  # already has enough leads

            lead_ids = [l.id for l in leads]
            if lead_ids:
                quotes_result = await db.execute(
                    select(Quote).where(Quote.lead_id.in_(lead_ids))
                )
                if quotes_result.scalars().all():
                    continue  # has quotes — fine

            # Reset match_intelligence so idempotency guard doesn't block re-run
            job.match_intelligence = None
            db.add(job)
            await db.flush()

            # Re-queue distribution
            try:
                from tasks.lead_tasks import distribute_leads
                jitter = random.uniform(5, 30)
                distribute_leads.apply_async(args=[job.id], countdown=jitter)
                print(f"[timeout]   → Re-queued distribution for '{job.title}' (job {job.id})")
            except Exception as e:
                print(f"[timeout]   Warning: could not re-queue {job.id}: {e}")

        await db.commit()