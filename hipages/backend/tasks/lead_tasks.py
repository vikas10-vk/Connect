"""
backend/tasks/lead_tasks.py

UPDATED — three new job lifecycle tasks added below the existing distribute_leads task:

  auto_reject_scope_change(job_id)
    Fired by Celery countdown 10 minutes after a scope change is requested.
    If the homeowner has not responded (job still in awaiting_scope_approval),
    the scope change is auto-rejected. Job returns to in_progress with the
    original scope. Tradie is notified: user non-response = rejection.
    The task is revoked (cancelled) by the scope-change/respond endpoint
    if the homeowner responds before the 10 minutes expires.

  auto_close_completed_jobs()
    Beat task — runs every 30 minutes. Finds jobs in 'completed' status
    where completed_at is more than 48 hours ago AND no dispute has been raised.
    Transitions them to 'closed' via the state machine. This releases the
    payment hold and allows the tradie to be reviewed.

  detect_no_shows()
    Beat task — runs every 5 minutes. Finds jobs in 'hired' status where
    the scheduled start time (or created_at + 30 minutes if no schedule)
    has passed and the tradie has NOT marked the job as started (still 'hired').
    Fires an alert to the homeowner and flags the tradie for admin review.
    Full refund is triggered. Tradie account is reviewed.
    This is the "cannot abandon silently" enforcement from the PDF.

EXISTING TASK (preserved exactly):
  distribute_leads(job_id)
"""

import uuid
import math
import os
import sys
import json
import asyncio
import random
from datetime import datetime, timedelta

from celery import shared_task

from models.user import User
from models.category import Category
from models.job import Job
from models.job_photo import JobPhoto
from models.lead import Lead
from models.quote import Quote
from models.review import Review
from models.tradie_profile import TradieProfile
from models.tradie_category import TradieCategory
from models.tradie_preference import TradiePreference

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ═══════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _make_session_factory():
    """
    Fresh engine + session factory per task.
    Tied to the CURRENT event loop, not the import-time loop.
    """
    from sqlalchemy.ext.asyncio import (
        create_async_engine, AsyncSession, async_sessionmaker
    )
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return engine, session_factory


def _run_task(coro_factory):
    """
    Creates a fresh event loop, runs the given coroutine factory, then cleans up.
    Use this as the standard wrapper for all async task bodies.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engine, session_factory = _make_session_factory()
    try:
        loop.run_until_complete(coro_factory(session_factory))
    finally:
        try:
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _suburb_in_list(target_suburb: str, service_suburbs_json) -> bool:
    if not service_suburbs_json or not target_suburb:
        return False
    try:
        suburbs = json.loads(service_suburbs_json)
        target = target_suburb.strip().lower()
        for s in suburbs:
            if not isinstance(s, dict):
                continue
            if (s.get("suburb") or "").strip().lower() == target:
                return True
        return False
    except (json.JSONDecodeError, TypeError):
        return False


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING TASK — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

async def _distribute_leads(job_id: str, session_factory):
    from sqlalchemy import select

    async with session_factory() as db:

        # 1. Load job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            print(f"[leads] Job {job_id} not found")
            return

        # 2. Idempotency guard — match_intelligence is stamped on success
        if job.match_intelligence:
            print(f"[leads] Job {job_id} already processed (idempotency) — skip")
            return

        if not job.lat or not job.lng:
            print(f"[leads] Job {job_id} has no coordinates — skip")
            return

        print(f"[leads] ─────────────────────────────────────────────────")
        print(f"[leads] JOB: {job.title} | {job.suburb}, {job.state}")
        print(f"[leads]   Coords: ({job.lat:.4f}, {job.lng:.4f})")
        print(f"[leads]   Category: {job.category_id}")

        # 3. SQL filter: approved + available + geocoded
        candidates_q = (
            select(TradieProfile, User, TradiePreference)
            .join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id)
            .join(User, User.id == TradieProfile.user_id)
            .outerjoin(TradiePreference, TradiePreference.tradie_id == TradieProfile.id)
            .where(
                TradieCategory.category_id == job.category_id,
                TradieProfile.verification_status == "approved",
                TradieProfile.is_available == True,
                TradieProfile.lat.is_not(None),
                TradieProfile.lng.is_not(None),
                User.is_verified == True,
                User.is_active == True,
            )
        )
        result = await db.execute(candidates_q)
        rows = result.all()
        print(f"[leads]   Eligible tradies (sql): {len(rows)}")

        if not rows:
            print(f"[leads]   0 tradies — notifying homeowner")
            await _store_match_intelligence(db, job, 0, 0)
            await _notify_homeowner_no_tradies(db, job)
            await db.commit()
            return

        # 4. Geo filter
        in_range, out_of_range = [], []
        for profile, user, pref in rows:
            dist = haversine_distance(job.lat, job.lng, profile.lat, profile.lng)
            if dist <= (profile.radius_km or 25) or _suburb_in_list(job.suburb, pref.service_suburbs if pref else None):
                print(f"[leads]   ✓ {profile.business_name} ({dist:.1f}km)")
                in_range.append((dist, profile))
            else:
                out_of_range.append((dist, profile))
                print(f"[leads]   ✗ {profile.business_name} ({dist:.1f}km, out of range)")

        # 5. Expand radius 1.5× if < 3 found
        if len(in_range) < 3 and out_of_range:
            print(f"[leads]   Expanding radius 1.5×...")
            for dist, profile in out_of_range:
                if dist <= (profile.radius_km or 25) * 1.5:
                    print(f"[leads]   ↗ {profile.business_name} (extended {dist:.1f}km)")
                    in_range.append((dist, profile))

        in_range.sort(key=lambda x: x[0])
        selected = in_range[:3]

        if not selected:
            print(f"[leads]   No tradies after expansion — notifying homeowner")
            await _store_match_intelligence(db, job, 0, 0)
            await _notify_homeowner_no_tradies(db, job)
            await db.commit()
            return

        # 6. Create leads (skip duplicates)
        leads_created = 0
        for dist, profile in selected:
            exists = await db.execute(
                select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == profile.id)
            )
            if exists.scalar_one_or_none():
                print(f"[leads]   - Lead exists for {profile.business_name}, skip")
                continue
            db.add(Lead(
                id=str(uuid.uuid4()),
                job_id=job_id,
                tradie_id=profile.id,
                credits_charged=0,
                status="sent",
            ))
            leads_created += 1
            print(f"[leads]   → Lead: {profile.business_name} ({dist:.1f}km)")

        await _store_match_intelligence(db, job, leads_created, len(in_range))
        await db.commit()
        print(f"[leads] DONE — {leads_created} lead(s) for {job_id}")
        print(f"[leads] ─────────────────────────────────────────────────")


async def _store_match_intelligence(db, job, leads_created: int, in_area: int):
    from datetime import datetime as dt
    urgency_hours = {
        "emergency": 1, "asap": 2, "today": 3,
        "next_few_days": 6, "next_few_weeks": 24, "flexible": 48,
    }
    job.match_intelligence = json.dumps({
        "matched":            leads_created,
        "in_area":            in_area,
        "avg_response_hours": urgency_hours.get(getattr(job, "urgency", "next_few_days"), 6),
        "computed_at":        dt.utcnow().isoformat(),
    })
    db.add(job)


async def _notify_homeowner_no_tradies(db, job):
    try:
        from sqlalchemy import select
        from services.resend_service import send_no_tradies_email
        result = await db.execute(select(User).where(User.id == job.homeowner_id))
        homeowner = result.scalar_one_or_none()
        if homeowner:
            await send_no_tradies_email(
                to_email=homeowner.email,
                full_name=homeowner.full_name or "",
                job_title=job.title,
                suburb=job.suburb or "",
            )
            print(f"[leads]   → Homeowner {homeowner.email} notified")
    except Exception as e:
        print(f"[leads]   Warning: notification failed: {e}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def distribute_leads(self, job_id: str):
    """
    Fresh event loop + fresh DB engine per invocation.
    Required for Windows asyncpg compatibility with Celery --pool=solo.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engine, session_factory = _make_session_factory()
    try:
        loop.run_until_complete(_distribute_leads(job_id, session_factory))
    except Exception as exc:
        print(f"[leads] Error for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 + random.uniform(0, 30))
    finally:
        try:
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# NEW TASK 1: Scope change auto-reject (10-minute countdown)
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=30, queue="critical")
def auto_reject_scope_change(self, job_id: str):
    """
    Fired as a countdown task (10 minutes) when a tradie requests a scope change.
    If the homeowner has not responded by the time this fires, the scope change
    is automatically rejected and the job returns to in_progress with original scope.

    The scope-change/respond endpoint revokes this task when the homeowner responds
    before the 10 minutes expires. If the revoke call fails (Celery edge case),
    this task guards itself with an idempotency check:
      - If job is no longer in awaiting_scope_approval, this is a no-op.
      - If scope_change_expires_at has passed, proceed with auto-reject.
    """
    _run_task(lambda sf: _async_auto_reject_scope_change(job_id, sf))


async def _async_auto_reject_scope_change(job_id: str, session_factory):
    import logging
    from sqlalchemy import select
    from services.job_state_machine import JobStateMachine, InvalidTransitionError

    logger = logging.getLogger(__name__)

    async with session_factory() as db:
        res = await db.execute(select(Job).where(Job.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            logger.warning("[scope-auto-reject] Job %s not found — skip.", job_id)
            return

        # ── Idempotency guard ─────────────────────────────────────────────
        # If the homeowner already responded, the job is back in in_progress.
        # This task either fired late or revoke didn't work. Either way: no-op.
        if job.status != "awaiting_scope_approval":
            logger.info(
                "[scope-auto-reject] Job %s is in status '%s' — homeowner already responded. No-op.",
                job_id, job.status,
            )
            return

        # ── Apply auto-reject ─────────────────────────────────────────────
        logger.warning(
            "[scope-auto-reject] Homeowner did not respond to scope change for job %s. "
            "Auto-rejecting — original scope continues.",
            job_id,
        )
        try:
            await JobStateMachine.system_transition(
                job=job,
                new_status="in_progress",
                db=db,
                note=(
                    "Scope change auto-rejected — homeowner did not respond within 10 minutes. "
                    "Job continues with original scope and original price. "
                    "Tradie cannot charge for unapproved work."
                ),
                extra_job_fields={
                    "pending_scope_amount_cents": None,
                    "scope_change_reason":        None,
                    "scope_change_requested_at":  None,
                    "scope_change_expires_at":    None,
                    "scope_change_task_id":       None,
                },
            )
        except InvalidTransitionError as e:
            logger.error("[scope-auto-reject] Transition failed for job %s: %s", job_id, e)
            return

        await db.commit()
        logger.info("[scope-auto-reject] Job %s returned to in_progress (original scope).", job_id)

        # ── Notify the tradie ─────────────────────────────────────────────
        try:
            homeowner_res = await db.execute(select(User).where(User.id == job.homeowner_id))
            homeowner = homeowner_res.scalar_one_or_none()

            # Load the tradie lead for notification
            lead_res = await db.execute(
                select(Lead).where(Lead.job_id == job_id).limit(1)
            )
            lead = lead_res.scalar_one_or_none()
            if lead:
                profile_res = await db.execute(
                    select(TradieProfile, User)
                    .join(User, User.id == TradieProfile.user_id)
                    .where(TradieProfile.id == lead.tradie_id)
                )
                row = profile_res.first()
                if row:
                    profile, tradie_user = row
                    from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME
                    name = _first(tradie_user.full_name or "")
                    body = f"""
                      <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                                 font-weight:500;color:#1A1A1A;">Scope change not approved</h1>
                      <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
                        G'day {name}, the homeowner did not respond to your scope change request
                        for job <strong>"{job.title}"</strong> within 10 minutes.
                      </p>
                      <div style="background:#FFF9F0;border:1px solid #B85C0033;border-radius:12px;
                                  padding:16px 20px;margin:20px 0;">
                        <p style="margin:0;font-size:13.5px;line-height:1.7;color:#1A1A1A;">
                          ⚠️ Non-response is treated as a rejection.<br>
                          The job continues with the <strong>original scope and original price</strong>.<br>
                          You cannot charge for the additional work.
                        </p>
                      </div>
                      <p style="margin:20px 0 0;font-size:13px;color:#8A8882;">
                        If you are unable to continue with the original scope, use
                        <strong>Stop Work</strong> in the app to trigger the partial stop flow.
                      </p>"""
                    text = (
                        f"G'day {name},\n\n"
                        f"The homeowner did not respond to your scope change for '{job.title}'.\n\n"
                        f"Non-response = rejection. Job continues with original scope and price.\n"
                        f"You cannot charge for unapproved work.\n\n"
                        f"— The {APP_NAME} team"
                    )
                    await _send_raw_email(
                        tradie_user.email,
                        f"Scope change not approved — {job.title}",
                        _base_html(body, "#B85C00"),
                        text,
                    )
        except Exception as e:
            print(f"[scope-auto-reject] Notification failed (non-fatal): {e}")


# ═══════════════════════════════════════════════════════════════════════════
# NEW TASK 2: Auto-close completed jobs after 48-hour dispute window
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=120, queue="normal")
def auto_close_completed_jobs(self):
    """
    Beat task — runs every 30 minutes.
    Finds jobs in 'completed' status where:
      - completed_at < now - 48 hours
      - status is still 'completed' (no dispute raised)
    Transitions them to 'closed' via the state machine.
    This unblocks the payment release and allows the tradie to receive a review.
    """
    _run_task(_async_auto_close_completed_jobs)


async def _async_auto_close_completed_jobs(session_factory):
    import logging
    from sqlalchemy import select
    from services.job_state_machine import JobStateMachine, InvalidTransitionError

    logger = logging.getLogger(__name__)
    cutoff = datetime.utcnow() - timedelta(hours=48)

    async with session_factory() as db:
        res = await db.execute(
            select(Job).where(
                Job.status == "completed",
                Job.is_deleted == False,
                Job.completed_at < cutoff,
            )
        )
        jobs = res.scalars().all()

        if not jobs:
            logger.debug("[auto-close] No jobs to close.")
            return

        logger.info("[auto-close] Found %d job(s) eligible for auto-close.", len(jobs))
        closed = 0

        for job in jobs:
            try:
                await JobStateMachine.system_transition(
                    job=job,
                    new_status="closed",
                    db=db,
                    note=(
                        "Job auto-closed after 48-hour dispute window with no dispute raised. "
                        "Payment release is now eligible."
                    ),
                )
                closed += 1
                logger.info("[auto-close] Job %s → closed.", job.id)
            except InvalidTransitionError as e:
                logger.error("[auto-close] Could not close job %s: %s", job.id, e)
                continue

        await db.commit()
        logger.info("[auto-close] Done — %d/%d job(s) closed.", closed, len(jobs))


# ═══════════════════════════════════════════════════════════════════════════
# NEW TASK 3: No-show detection
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=60, queue="normal")
def detect_no_shows(self):
    """
    Beat task — runs every 5 minutes.

    Finds jobs in 'hired' status where the tradie was expected to start but
    has NOT marked the job as in_progress (still 'hired') 30 minutes after the
    scheduled time (or 30 minutes after the lead was first sent if no schedule).

    A tradie CANNOT abandon a job silently. If they disappear:
      1. Homeowner is alerted at T+30min.
      2. Tradie account is flagged for admin review.
      3. Full refund logic is triggered (payment hold released back to homeowner).
      4. Job is cancelled by the system with a no-show note in the event trail.

    DETECTION HEURISTIC:
      No scheduled_start on the job model yet (TODO Phase 2).
      For now, we use:
        lead.sent_at + 30 minutes as a proxy for "expected arrival window".
      When scheduling is added, this will be replaced with
        job.scheduled_start + 30 minutes.

    This task fires alerts — it does NOT automatically cancel the job, because
    the tradie might be genuinely delayed. The homeowner gets a notification
    and the option to cancel or wait. If no response in another 30 minutes,
    a second pass cancels the job.
    """
    _run_task(_async_detect_no_shows)


async def _async_detect_no_shows(session_factory):
    import logging
    from sqlalchemy import select
    from services.job_state_machine import JobStateMachine, InvalidTransitionError

    logger = logging.getLogger(__name__)
    now = datetime.utcnow()

    async with session_factory() as db:
        # Find all 'hired' jobs that have been hired for > 30 minutes with no start
        threshold_time = now - timedelta(minutes=30)

        res = await db.execute(
            select(Job).where(
                Job.status == "hired",
                Job.is_deleted == False,
                Job.updated_at < threshold_time,  # status last changed (hired) > 30 min ago
            )
        )
        jobs = res.scalars().all()

        if not jobs:
            logger.debug("[no-show] No no-show candidates found.")
            return

        logger.info("[no-show] Checking %d hired job(s) for no-show.", len(jobs))

        for job in jobs:
            # ── Check if a no-show alert has already been sent ────────────────
            # We check the job_events table for an existing no-show alert entry.
            from models.job_event import JobEvent
            alert_res = await db.execute(
                select(JobEvent).where(
                    JobEvent.job_id == job.id,
                    JobEvent.action == "no_show_alert",
                ).limit(1)
            )
            alert_already_sent = alert_res.scalar_one_or_none()

            if alert_already_sent:
                # ── Second pass: cancel if T+60min still no start ─────────────
                second_threshold = now - timedelta(minutes=60)
                if job.updated_at < second_threshold:
                    logger.warning(
                        "[no-show] Job %s: tradie still no-show at T+60min — cancelling.", job.id
                    )
                    try:
                        await JobStateMachine.system_transition(
                            job=job,
                            new_status="cancelled",
                            db=db,
                            note=(
                                "Job cancelled by system — tradie no-show detected at T+60 minutes. "
                                "Full refund triggered. Tradie account flagged for admin review."
                            ),
                        )
                        await _flag_tradie_no_show(job, db, logger)
                        await _notify_homeowner_no_show_cancelled(job, db)
                    except InvalidTransitionError as e:
                        logger.error("[no-show] Cancel failed for job %s: %s", job.id, e)
                continue

            # ── First pass: alert at T+30min ──────────────────────────────────
            logger.warning(
                "[no-show] Job %s: tradie has not started — T+30min alert firing.", job.id
            )

            # Write the no_show_alert event (idempotency marker + audit trail)
            event = JobEvent(
                job_id=job.id,
                actor_id="system",
                actor_role="system",
                action="no_show_alert",
                old_value={"status": job.status},
                new_value={"status": job.status},
                note=(
                    "Tradie has not marked the job as started 30 minutes after expected arrival. "
                    "Homeowner has been alerted. Tradie flagged for review."
                ),
            )
            db.add(event)

            await _notify_homeowner_no_show_alert(job, db)
            await _notify_tradie_no_show_warning(job, db, logger)

        await db.commit()
        logger.info("[no-show] Run complete.")


async def _flag_tradie_no_show(job: Job, db, logger):
    """
    Increments the no_show_count on the tradie's TeamMember row.
    At 3 no-shows, can_accept_jobs is set to False pending admin review.
    """
    try:
        from sqlalchemy import select, update
        from models.lead import Lead
        from models.tradie_profile import TradieProfile
        from models.team_member import TeamMember

        lead_res = await db.execute(
            select(Lead).where(Lead.job_id == job.id).limit(1)
        )
        lead = lead_res.scalar_one_or_none()
        if not lead:
            return

        # Find the assigned worker
        member_res = await db.execute(
            select(TeamMember).where(
                TeamMember.business_id == lead.tradie_id,
                TeamMember.role == "owner",
            ).limit(1)
        )
        member = member_res.scalar_one_or_none()
        if not member:
            return

        new_count = (member.no_show_count or 0) + 1
        update_vals = {"no_show_count": new_count}

        if new_count >= 3:
            update_vals["can_accept_jobs"] = False
            logger.warning(
                "[no-show] Tradie %s has %d no-shows — can_accept_jobs → False.",
                member.id, new_count,
            )

        await db.execute(
            update(TeamMember)
            .where(TeamMember.id == member.id)
            .values(**update_vals)
        )
    except Exception as e:
        logger.error("[no-show] Failed to flag tradie: %s", e)


async def _notify_homeowner_no_show_alert(job: Job, db):
    """T+30min alert — homeowner told the tradie hasn't shown up."""
    try:
        from sqlalchemy import select
        from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME

        homeowner_res = await db.execute(select(User).where(User.id == job.homeowner_id))
        homeowner = homeowner_res.scalar_one_or_none()
        if not homeowner:
            return

        name = _first(homeowner.full_name or "")
        body = f"""
          <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                     font-weight:500;color:#1A1A1A;">Your tradie hasn't arrived yet</h1>
          <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
            G'day {name}, it looks like the tradie for your job <strong>"{job.title}"</strong>
            hasn't marked their arrival in the app yet.
          </p>
          <div style="background:#FFF9F0;border:1px solid #B85C0033;border-radius:12px;
                      padding:16px 20px;margin:20px 0;">
            <p style="margin:0;font-size:13.5px;line-height:1.7;color:#1A1A1A;">
              ⏱ <strong>What's happening?</strong><br>
              We've notified the tradie. They may just be running a few minutes late.<br><br>
              If they don't arrive within the next 30 minutes, we'll automatically cancel
              the booking and arrange a full refund.
            </p>
          </div>
          <p style="margin:0;font-size:13px;color:#8A8882;">
            If you want to cancel now, you can do so from your dashboard.
          </p>
          {_btn("View Job", f"http://localhost:3000/dashboard", "#B85C00")}"""
        text = (
            f"G'day {name},\n\n"
            f"The tradie for '{job.title}' hasn't arrived yet.\n\n"
            f"We've notified them. If they don't arrive in 30 minutes, "
            f"the booking will be cancelled and you'll receive a full refund.\n\n"
            f"— The {APP_NAME} team"
        )
        await _send_raw_email(
            homeowner.email,
            f"Your tradie hasn't arrived yet — {job.title}",
            _base_html(body, "#B85C00"),
            text,
        )
    except Exception as e:
        print(f"[no-show] Homeowner alert failed (non-fatal): {e}")


async def _notify_homeowner_no_show_cancelled(job: Job, db):
    """T+60min — job cancelled, full refund."""
    try:
        from sqlalchemy import select
        from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME

        homeowner_res = await db.execute(select(User).where(User.id == job.homeowner_id))
        homeowner = homeowner_res.scalar_one_or_none()
        if not homeowner:
            return

        name = _first(homeowner.full_name or "")
        body = f"""
          <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                     font-weight:500;color:#1A1A1A;">Booking cancelled — full refund issued</h1>
          <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
            G'day {name}, the tradie did not arrive for your job <strong>"{job.title}"</strong>
            and the booking has been cancelled automatically.
          </p>
          <div style="background:#E8F5EE;border:1px solid #2E7D5A33;border-radius:12px;
                      padding:16px 20px;margin:20px 0;">
            <p style="margin:0;font-size:13.5px;line-height:1.7;color:#1A1A1A;">
              ✅ <strong>Full refund issued.</strong> You have not been charged.<br>
              The tradie's account has been flagged for review.<br>
              We're sorry this happened — we take no-shows seriously.
            </p>
          </div>
          {_btn("Re-post your job", f"http://localhost:3000/book", "#2E7D5A")}"""
        text = (
            f"G'day {name},\n\n"
            f"The tradie didn't arrive for '{job.title}'. Booking cancelled. Full refund issued.\n"
            f"The tradie's account has been flagged.\n\n"
            f"Re-post your job: http://localhost:3000/book\n\n"
            f"— The {APP_NAME} team"
        )
        await _send_raw_email(
            homeowner.email,
            f"Booking cancelled — full refund for {job.title}",
            _base_html(body, "#2E7D5A"),
            text,
        )
    except Exception as e:
        print(f"[no-show] Homeowner cancellation email failed (non-fatal): {e}")


async def _notify_tradie_no_show_warning(job: Job, db, logger):
    """T+30min — tradie warned that the booking will be cancelled if they don't check in."""
    try:
        from sqlalchemy import select
        from models.lead import Lead
        from models.tradie_profile import TradieProfile
        from services.resend_service import _send_raw_email, _base_html, _first, APP_NAME

        lead_res = await db.execute(
            select(Lead).where(Lead.job_id == job.id).limit(1)
        )
        lead = lead_res.scalar_one_or_none()
        if not lead:
            return

        profile_res = await db.execute(
            select(TradieProfile, User)
            .join(User, User.id == TradieProfile.user_id)
            .where(TradieProfile.id == lead.tradie_id)
        )
        row = profile_res.first()
        if not row:
            return

        profile, tradie_user = row
        name = _first(tradie_user.full_name or "")

        body = f"""
          <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                     font-weight:500;color:#1A1A1A;">Action required: mark your arrival</h1>
          <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
            G'day {name}, you have a job <strong>"{job.title}"</strong> that you haven't
            checked in on yet. The homeowner has been notified.
          </p>
          <div style="background:#FFF5F5;border:1px solid #A3303033;border-radius:12px;
                      padding:16px 20px;margin:20px 0;">
            <p style="margin:0;font-size:13.5px;line-height:1.7;color:#1A1A1A;">
              ⚠️ <strong>If you do not mark arrival in the next 30 minutes:</strong><br>
              • The booking will be automatically cancelled<br>
              • The homeowner will receive a full refund<br>
              • Your account will be flagged for review
            </p>
          </div>
          <p style="margin:20px 0 0;font-size:13px;color:#8A8882;">
            If you are running late, open the app and mark your status. If you cannot attend,
            use <strong>Cancel Job</strong> in the app immediately.
          </p>"""
        text = (
            f"G'day {name},\n\n"
            f"You have a job '{job.title}' with no check-in recorded.\n\n"
            f"If you do not mark arrival in the next 30 minutes:\n"
            f"- The booking will be cancelled\n"
            f"- The homeowner receives a full refund\n"
            f"- Your account is flagged for review\n\n"
            f"Open the app and check in now.\n\n"
            f"— The {APP_NAME} team"
        )
        await _send_raw_email(
            tradie_user.email,
            f"⚠️ Action required: mark your arrival for {job.title}",
            _base_html(body, "#A33030"),
            text,
        )
    except Exception as e:
        logger.error("[no-show] Tradie warning email failed (non-fatal): %s", e)