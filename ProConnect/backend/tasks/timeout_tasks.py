import asyncio
import json
import random
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import select

from db.session import AsyncSessionLocal

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
        raise self.retry(exc=exc) from exc
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _check_stale_jobs():
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
    Runs every 6 hours (beat schedule).

    Two-pass strategy for un-matched open jobs:

    Pass A — Classic stale jobs (> 48h old, < 3 leads, no quotes):
      Re-triggers distribute_leads with a wider radius so jobs get coverage
      even if no tradies were in the original radius.

    Pass B — Zero-lead safety net (last 30 days, < 48h old):
      Catches open jobs where match_intelligence.matched == 0, meaning
      distribution ran but found nobody. Primary coverage comes from the
      event-driven redistribute_open_jobs_for_tradie task fired when a
      tradie gets verified. This pass is the fallback for anything that
      slipped through (Celery downtime, bulk verification imports, etc.).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_redistribute_stale_jobs())
    except Exception as exc:
        print(f"[timeout] redistribute_stale_jobs error: {exc}")
        raise self.retry(exc=exc) from exc
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
    cutoff_48h   = now - timedelta(hours=48)   # stale: older than 48h
    lookback_30d = now - timedelta(days=30)    # zero-lead safety net: last 30 days

    async with AsyncSessionLocal() as db:

        # ── Pass A: Classic stale jobs (> 48h old, < 3 leads, no quotes) ──
        result = await db.execute(
            select(Job)
            .where(
                Job.status == 'open',
                Job.is_deleted == False,
                Job.created_at < cutoff_48h,
            )
        )
        stale_jobs = result.scalars().all()
        print(f"[timeout] Pass A — {len(stale_jobs)} jobs older than 48h for re-distribution...")

        requeued_a = 0
        for job in stale_jobs:
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
                    continue  # has quotes — homeowner is being served

            # Reset match_intelligence so idempotency guard doesn't block re-run
            job.match_intelligence = None
            db.add(job)
            await db.flush()

            try:
                from tasks.lead_tasks import distribute_leads
                jitter = random.uniform(5, 30)
                distribute_leads.apply_async(args=[job.id], countdown=jitter)
                print(f"[timeout]   → Re-queued '{job.title}' ({job.id})")
                requeued_a += 1
            except Exception as e:
                print(f"[timeout]   Warning: could not re-queue {job.id}: {e}")

        # ── Pass B: Zero-lead safety net (last 30 days, < 48h old) ────────
        # Targets ONLY jobs where distribution already ran (match_intelligence
        # is not NULL) but returned 0 matches. This avoids interfering with
        # jobs that simply haven't been distributed yet.
        #
        # The primary handler for this scenario is the event-driven task
        # redistribute_open_jobs_for_tradie (fired on tradie verification).
        # This pass is the safety net for edge cases: Celery downtime,
        # bulk admin verification imports, etc.
        result_b = await db.execute(
            select(Job)
            .where(
                Job.status == 'open',
                Job.is_deleted == False,
                Job.created_at >= lookback_30d,
                Job.created_at >= cutoff_48h,         # < 48h — Pass A handles older
                Job.match_intelligence.isnot(None),   # must have been attempted
            )
        )
        recent_candidates = result_b.scalars().all()

        zero_lead_jobs = []
        for job in recent_candidates:
            try:
                mi = json.loads(job.match_intelligence)
                if mi.get("matched", 0) == 0:
                    zero_lead_jobs.append(job)
            except Exception:
                pass

        print(
            f"[timeout] Pass B — {len(zero_lead_jobs)} recent 0-lead open jobs "
            f"(late-subscriber safety net)"
        )

        requeued_b = 0
        for job in zero_lead_jobs:
            # Double-check: no actual leads in DB either
            leads_check = await db.execute(
                select(Lead).where(Lead.job_id == job.id)
            )
            if leads_check.scalars().all():
                continue  # leads exist despite mi saying 0 — stale intelligence, skip

            job.match_intelligence = None
            db.add(job)
            await db.flush()

            try:
                from tasks.lead_tasks import distribute_leads
                jitter = random.uniform(30, 90)  # longer jitter — less urgent than Pass A
                distribute_leads.apply_async(args=[job.id], countdown=jitter)
                print(f"[timeout]   → (B) Re-queued '{job.title}' ({job.id})")
                requeued_b += 1
            except Exception as e:
                print(f"[timeout]   Warning (B): could not re-queue {job.id}: {e}")

        await db.commit()
        print(
            f"[timeout] redistribute_stale_jobs complete — "
            f"Pass A: {requeued_a} re-queued, Pass B: {requeued_b} re-queued"
        )
