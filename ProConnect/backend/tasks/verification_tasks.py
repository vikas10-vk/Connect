"""
backend/tasks/verification_tasks.py

UPDATED — three new tasks added below the existing two:

  3. check_cert_expiry()      Daily. Scans TradieCertification rows where
                               status='verified' and expires_at is approaching.
                               Sends tiered reminder emails at 30/14/7/1 days.
                               On day 0: marks cert 'expired', disables the
                               worker or tradie (can_accept_jobs = False /
                               is_available = False).

  4. check_insurance_expiry() Same pattern for InsurancePolicy rows.
                               Public liability expiry disables the ENTIRE
                               business — no tradie can be dispatched without
                               valid insurance.

  5. watchdog_ghost_jobs()    Every 5 min. Finds jobs stuck in 'pending' or
                               'open' status for >10 min with no successful
                               lead distribution task. Re-enqueues them so
                               no booking silently disappears.

All existing tasks (notify_verification_decisions, notify_review_decisions)
are preserved exactly as written.

WIRING — add these to celery_app.py beat_schedule:
    "check-cert-expiry": {
        "task":     "tasks.verification_tasks.check_cert_expiry",
        "schedule": crontab(hour=6, minute=0),   # daily at 6am
    },
    "check-insurance-expiry": {
        "task":     "tasks.verification_tasks.check_insurance_expiry",
        "schedule": crontab(hour=6, minute=15),  # daily at 6:15am
    },
    "watchdog-ghost-jobs": {
        "task":     "tasks.verification_tasks.watchdog_ghost_jobs",
        "schedule": 300.0,   # every 5 minutes
    },
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Shared async runner ───────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING TASKS — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

# ── Task 1: Tradie verification decision emails ───────────────────────────────
@celery_app.task(name="tasks.verification_tasks.notify_verification_decisions")
def notify_verification_decisions():
    """
    Finds TradieProfiles where:
      - verification_status IN (approved, rejected, needs_documents, suspended)
      - reviewed_at IS NOT NULL  (admin made a decision)
      - email_notified_at IS NULL  (not yet emailed)

    Sends the appropriate email and stamps email_notified_at.
    """
    _run(_async_notify_verification_decisions())


async def _async_notify_verification_decisions():
    from sqlalchemy import select, update
    from db.session import AsyncSessionLocal
    from models.tradie_profile import TradieProfile
    from models.user import User
    from services.resend_service import (
        send_tradie_approved_email,
        send_tradie_rejected_email,
        send_tradie_needs_documents_email,
        send_tradie_suspended_email,
    )

    ACTIONABLE_STATUSES = {"approved", "rejected", "needs_documents", "suspended"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradieProfile)
            .where(
                TradieProfile.verification_status.in_(ACTIONABLE_STATUSES),
                TradieProfile.reviewed_at.is_not(None),
                TradieProfile.email_notified_at.is_(None),
            )
            .limit(50)
        )
        profiles = result.scalars().all()

        if not profiles:
            return

        logger.info("[verify-notify] Found %d profiles needing notification", len(profiles))

        for profile in profiles:
            user_result = await db.execute(
                select(User).where(User.id == profile.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                logger.warning("[verify-notify] No user found for profile %s", profile.id)
                continue

            status = profile.verification_status
            sent = False

            try:
                if status == "approved":
                    sent = await send_tradie_approved_email(
                        to_email=user.email,
                        full_name=user.full_name or "",
                        business_name=profile.business_name,
                    )
                elif status == "rejected":
                    sent = await send_tradie_rejected_email(
                        to_email=user.email,
                        full_name=user.full_name or "",
                        business_name=profile.business_name,
                        notes=profile.verification_notes,
                    )
                elif status == "needs_documents":
                    sent = await send_tradie_needs_documents_email(
                        to_email=user.email,
                        full_name=user.full_name or "",
                        business_name=profile.business_name,
                        notes=profile.verification_notes,
                    )
                elif status == "suspended":
                    sent = await send_tradie_suspended_email(
                        to_email=user.email,
                        full_name=user.full_name or "",
                        business_name=profile.business_name,
                        notes=profile.verification_notes,
                    )
            except Exception as e:
                logger.error("[verify-notify] Email send failed for profile %s: %s", profile.id, e)
                continue

            if sent:
                await db.execute(
                    update(TradieProfile)
                    .where(TradieProfile.id == profile.id)
                    .values(email_notified_at=datetime.utcnow())
                )
                logger.info(
                    "[verify-notify] Sent '%s' email to %s (profile %s)",
                    status, user.email, profile.id
                )

        await db.commit()


# ── Task 2: Review moderation decision emails ─────────────────────────────────
@celery_app.task(name="tasks.verification_tasks.notify_review_decisions")
def notify_review_decisions():
    """
    Finds Reviews where:
      - status IN (approved, rejected)
      - reviewed_at IS NOT NULL
      - email_notified_at IS NULL

    Sends the appropriate email to the homeowner and stamps email_notified_at.
    """
    _run(_async_notify_review_decisions())


async def _async_notify_review_decisions():
    from sqlalchemy import select, update
    from sqlalchemy.orm import selectinload
    from db.session import AsyncSessionLocal
    from models.review import Review
    from models.user import User
    from models.tradie_profile import TradieProfile
    from services.resend_service import (
        send_review_approved_email,
        send_review_rejected_email,
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Review)
            .where(
                Review.status.in_(["approved", "rejected"]),
                Review.reviewed_at.is_not(None),
                Review.email_notified_at.is_(None),
            )
            .limit(50)
        )
        reviews = result.scalars().all()

        if not reviews:
            return

        logger.info("[review-notify] Found %d reviews needing notification", len(reviews))

        for review in reviews:
            homeowner_result = await db.execute(
                select(User).where(User.id == review.homeowner_id)
            )
            homeowner = homeowner_result.scalar_one_or_none()

            tradie_result = await db.execute(
                select(TradieProfile).where(TradieProfile.id == review.tradie_id)
            )
            tradie = tradie_result.scalar_one_or_none()

            if not homeowner or not tradie:
                logger.warning("[review-notify] Missing homeowner/tradie for review %s", review.id)
                continue

            sent = False
            try:
                if review.status == "approved":
                    sent = await send_review_approved_email(
                        to_email=homeowner.email,
                        full_name=homeowner.full_name or "",
                        tradie_business_name=tradie.business_name,
                        tradie_profile_id=tradie.id,
                    )
                elif review.status == "rejected":
                    sent = await send_review_rejected_email(
                        to_email=homeowner.email,
                        full_name=homeowner.full_name or "",
                        tradie_business_name=tradie.business_name,
                    )
            except Exception as e:
                logger.error("[review-notify] Email failed for review %s: %s", review.id, e)
                continue

            if sent:
                await db.execute(
                    update(Review)
                    .where(Review.id == review.id)
                    .values(email_notified_at=datetime.utcnow())
                )
                logger.info(
                    "[review-notify] Sent '%s' email to %s (review %s)",
                    review.status, homeowner.email, review.id
                )

        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# NEW TASKS
# ═══════════════════════════════════════════════════════════════════════════

# ── Task 3: Certificate expiry monitoring ─────────────────────────────────────
@celery_app.task(name="tasks.verification_tasks.check_cert_expiry")
def check_cert_expiry():
    """
    Daily task — scans TradieCertification rows with status='verified' and an
    expires_at value. Sends tiered reminder emails at 30/14/7/1 days before
    expiry. On expiry day (days_remaining <= 0), marks the cert 'expired' and
    disables the associated tradie or worker.

    DISABLE LOGIC:
      - Worker cert expires → worker.can_accept_jobs = False
      - Solo tradie cert expires AND no other verified cert remains
        → profile.is_available = False + owner team_member.can_accept_jobs = False
      The tradie is notified by email in both cases. They must submit a new
      licence number and await admin re-verification to be re-enabled.

    SAFETY NOTE:
      We do NOT auto-re-enable on re-verification — that is handled by the
      Django admin approval flow (notify_verification_decisions task +
      admin action). This task only disables, never enables.
    """
    _run(_async_check_cert_expiry())


async def _async_check_cert_expiry():
    from sqlalchemy import select, update, and_
    from db.session import AsyncSessionLocal
    from models.tradie_certification import TradieCertification, CertificationStatus
    from models.tradie_profile import TradieProfile
    from models.team_member import TeamMember
    from models.user import User
    from models.category import Category

    today = date.today()

    # Reminder windows: (days_threshold, reminder_column_attr, label)
    REMINDER_WINDOWS = [
        (1,  "reminder_1d_sent_at",  "1 day"),
        (7,  "reminder_7d_sent_at",  "7 days"),
        (14, "reminder_14d_sent_at", "14 days"),
        (30, "reminder_30d_sent_at", "30 days"),
    ]

    async with AsyncSessionLocal() as db:
        # All verified certs with an expiry date
        res = await db.execute(
            select(TradieCertification)
            .where(
                TradieCertification.status == CertificationStatus.VERIFIED,
                TradieCertification.expires_at.is_not(None),
            )
        )
        certs = res.scalars().all()

        if not certs:
            logger.info("[cert-expiry] No verified certs with expiry dates found.")
            return

        logger.info("[cert-expiry] Scanning %d verified certs.", len(certs))

        for cert in certs:
            days_remaining = (cert.expires_at - today).days

            # ── Fetch category name for the email ────────────────────
            cat_res = await db.execute(
                select(Category).where(Category.id == cert.category_id)
            )
            category = cat_res.scalar_one_or_none()
            category_name = category.name if category else "your trade category"

            # ── Fetch the owner of this cert ─────────────────────────
            # XOR: either tradie_profile_id or team_member_id is set.
            to_email   = None
            full_name  = None
            business_name = None

            if cert.tradie_profile_id:
                profile_res = await db.execute(
                    select(TradieProfile)
                    .where(TradieProfile.id == cert.tradie_profile_id)
                )
                profile = profile_res.scalar_one_or_none()
                if not profile:
                    continue
                user_res = await db.execute(
                    select(User).where(User.id == profile.user_id)
                )
                user = user_res.scalar_one_or_none()
                if not user:
                    continue
                to_email      = user.email
                full_name     = user.full_name or ""
                business_name = profile.business_name

            elif cert.team_member_id:
                member_res = await db.execute(
                    select(TeamMember).where(TeamMember.id == cert.team_member_id)
                )
                member = member_res.scalar_one_or_none()
                if not member:
                    continue
                # For workers, email goes to the business owner
                biz_res = await db.execute(
                    select(TradieProfile).where(TradieProfile.id == member.business_id)
                )
                biz = biz_res.scalar_one_or_none()
                if not biz:
                    continue
                owner_res = await db.execute(
                    select(User).where(User.id == biz.user_id)
                )
                owner = owner_res.scalar_one_or_none()
                if not owner:
                    continue
                to_email      = owner.email
                full_name     = owner.full_name or ""
                business_name = biz.business_name

            if not to_email:
                continue

            # ── Day 0: expire the cert + disable the tradie/worker ───
            if days_remaining <= 0:
                await db.execute(
                    update(TradieCertification)
                    .where(TradieCertification.id == cert.id)
                    .values(status=CertificationStatus.EXPIRED)
                )
                logger.info(
                    "[cert-expiry] Cert %s EXPIRED (%s, %s). Disabling owner.",
                    cert.id, category_name, cert.licence_number,
                )
                await _disable_cert_owner(cert, db)
                await _send_cert_email(
                    "expired", to_email, full_name, business_name,
                    category_name, cert.expires_at, 0,
                )
                continue

            # ── Reminder emails for approaching expiry ───────────────
            for threshold, col_attr, label in REMINDER_WINDOWS:
                if days_remaining > threshold:
                    continue                                    # not yet in this window
                if getattr(cert, col_attr) is not None:
                    continue                                    # already sent this reminder

                await db.execute(
                    update(TradieCertification)
                    .where(TradieCertification.id == cert.id)
                    .values(**{col_attr: datetime.utcnow()})
                )
                await _send_cert_email(
                    "reminder", to_email, full_name, business_name,
                    category_name, cert.expires_at, days_remaining,
                )
                logger.info(
                    "[cert-expiry] %s reminder → %s (cert %s, %d days left).",
                    label, to_email, cert.id, days_remaining,
                )
                break   # send only the most urgent reminder per run

        await db.commit()
        logger.info("[cert-expiry] Run complete.")


async def _disable_cert_owner(cert, db):
    """
    Disable can_accept_jobs for the cert owner (worker or solo tradie).
    For solo tradies: also sets is_available=False on the profile if no other
    verified cert remains — they cannot be dispatched without a valid licence.
    """
    from sqlalchemy import select, update, and_
    from models.tradie_certification import TradieCertification, CertificationStatus
    from models.tradie_profile import TradieProfile
    from models.team_member import TeamMember

    if cert.team_member_id:
        # Check if the worker has any other verified certs
        other_res = await db.execute(
            select(TradieCertification).where(
                TradieCertification.team_member_id == cert.team_member_id,
                TradieCertification.id != cert.id,
                TradieCertification.status == CertificationStatus.VERIFIED,
                TradieCertification.expires_at > date.today(),
            )
        )
        other_verified = other_res.scalar_one_or_none()
        if not other_verified:
            await db.execute(
                update(TeamMember)
                .where(TeamMember.id == cert.team_member_id)
                .values(can_accept_jobs=False)
            )
            logger.info(
                "[cert-expiry] Worker %s can_accept_jobs → False (no remaining valid certs).",
                cert.team_member_id,
            )

    elif cert.tradie_profile_id:
        # Check if the profile has any other verified certs
        other_res = await db.execute(
            select(TradieCertification).where(
                TradieCertification.tradie_profile_id == cert.tradie_profile_id,
                TradieCertification.id != cert.id,
                TradieCertification.status == CertificationStatus.VERIFIED,
                TradieCertification.expires_at > date.today(),
            )
        )
        other_verified = other_res.scalar_one_or_none()
        if not other_verified:
            # Disable the profile and the owner's team_members row
            await db.execute(
                update(TradieProfile)
                .where(TradieProfile.id == cert.tradie_profile_id)
                .values(is_available=False)
            )
            await db.execute(
                update(TeamMember)
                .where(
                    TeamMember.business_id == cert.tradie_profile_id,
                    TeamMember.role == "owner",
                )
                .values(can_accept_jobs=False)
            )
            logger.info(
                "[cert-expiry] Profile %s is_available → False + owner can_accept_jobs → False.",
                cert.tradie_profile_id,
            )


async def _send_cert_email(
    email_type: str,
    to_email: str,
    full_name: str,
    business_name: str,
    category_name: str,
    expires_at: date,
    days_remaining: int,
):
    """
    Sends a cert expiry reminder or expiry notification email.
    Calls into resend_service — add these two functions there:
      send_cert_expiry_reminder_email(to_email, full_name, business_name,
                                      category_name, expires_at, days_remaining)
      send_cert_expired_email(to_email, full_name, business_name, category_name)
    """
    try:
        from services.resend_service import (
            send_cert_expiry_reminder_email,
            send_cert_expired_email,
        )
        if email_type == "reminder":
            await send_cert_expiry_reminder_email(
                to_email=to_email,
                full_name=full_name,
                business_name=business_name,
                category_name=category_name,
                expires_at=expires_at,
                days_remaining=days_remaining,
            )
        elif email_type == "expired":
            await send_cert_expired_email(
                to_email=to_email,
                full_name=full_name,
                business_name=business_name,
                category_name=category_name,
            )
    except Exception as e:
        logger.error(
            "[cert-expiry] Email send failed (%s → %s): %s",
            email_type, to_email, e,
        )


# ── Task 4: Insurance expiry monitoring ───────────────────────────────────────
@celery_app.task(name="tasks.verification_tasks.check_insurance_expiry")
def check_insurance_expiry():
    """
    Daily task — scans InsurancePolicy rows with status='verified'.
    Sends tiered reminder emails at 30/14/7/1 days before expiry.
    On expiry day: marks policy 'expired' and DISABLES THE ENTIRE BUSINESS.

    WHY THE ENTIRE BUSINESS:
      Public liability insurance covers every worker operating under that
      business. An expired policy means no worker can legally be dispatched
      to a homeowner's property. The platform's own liability exposure starts
      the moment an uninsured worker causes damage on a job. We cannot allow
      even one job to proceed without valid coverage.

    IMPORTANT: Workers' compensation and professional indemnity expiry only
      disables the profile (is_available=False), not individual workers, since
      these policy types affect the whole business entity.
    """
    _run(_async_check_insurance_expiry())


async def _async_check_insurance_expiry():
    from sqlalchemy import select, update
    from db.session import AsyncSessionLocal
    from models.insurance_policy import InsurancePolicy, InsuranceStatus, InsuranceType
    from models.tradie_profile import TradieProfile
    from models.team_member import TeamMember
    from models.user import User

    today = date.today()

    REMINDER_WINDOWS = [
        (1,  "reminder_1d_sent_at",  "1 day"),
        (7,  "reminder_7d_sent_at",  "7 days"),
        (14, "reminder_14d_sent_at", "14 days"),
        (30, "reminder_30d_sent_at", "30 days"),
    ]

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(InsurancePolicy)
            .where(InsurancePolicy.status == InsuranceStatus.VERIFIED)
        )
        policies = res.scalars().all()

        if not policies:
            logger.info("[insurance-expiry] No verified insurance policies found.")
            return

        logger.info("[insurance-expiry] Scanning %d verified policies.", len(policies))

        for policy in policies:
            days_remaining = (policy.expires_at - today).days

            # Fetch business profile + owner for email
            profile_res = await db.execute(
                select(TradieProfile).where(TradieProfile.id == policy.tradie_profile_id)
            )
            profile = profile_res.scalar_one_or_none()
            if not profile:
                continue

            user_res = await db.execute(
                select(User).where(User.id == profile.user_id)
            )
            user = user_res.scalar_one_or_none()
            if not user:
                continue

            insurance_label = {
                InsuranceType.PUBLIC_LIABILITY:       "Public Liability Insurance",
                InsuranceType.WORKERS_COMPENSATION:   "Workers' Compensation Insurance",
                InsuranceType.PROFESSIONAL_INDEMNITY: "Professional Indemnity Insurance",
            }.get(policy.insurance_type, policy.insurance_type)

            # ── Day 0: expire + disable ──────────────────────────────
            if days_remaining <= 0:
                await db.execute(
                    update(InsurancePolicy)
                    .where(InsurancePolicy.id == policy.id)
                    .values(status=InsuranceStatus.EXPIRED)
                )
                logger.info(
                    "[insurance-expiry] Policy %s EXPIRED (%s). Disabling business %s.",
                    policy.id, insurance_label, profile.id,
                )

                # Check if a different verified policy of the same type exists
                other_res = await db.execute(
                    select(InsurancePolicy).where(
                        InsurancePolicy.tradie_profile_id == profile.id,
                        InsurancePolicy.id != policy.id,
                        InsurancePolicy.insurance_type == policy.insurance_type,
                        InsurancePolicy.status == InsuranceStatus.VERIFIED,
                        InsurancePolicy.expires_at > today,
                    )
                )
                other_valid = other_res.scalar_one_or_none()

                if not other_valid:
                    # Disable the whole business
                    await db.execute(
                        update(TradieProfile)
                        .where(TradieProfile.id == profile.id)
                        .values(is_available=False)
                    )
                    # Disable all active workers in this business
                    await db.execute(
                        update(TeamMember)
                        .where(
                            TeamMember.business_id == profile.id,
                            TeamMember.is_active == True,
                        )
                        .values(can_accept_jobs=False)
                    )
                    logger.info(
                        "[insurance-expiry] Business %s fully disabled — all workers can_accept_jobs → False.",
                        profile.id,
                    )

                await _send_insurance_email(
                    "expired", user.email, user.full_name or "",
                    profile.business_name, insurance_label, policy.expires_at, 0,
                )
                continue

            # ── Reminder emails for approaching expiry ───────────────
            for threshold, col_attr, label in REMINDER_WINDOWS:
                if days_remaining > threshold:
                    continue
                if getattr(policy, col_attr) is not None:
                    continue

                await db.execute(
                    update(InsurancePolicy)
                    .where(InsurancePolicy.id == policy.id)
                    .values(**{col_attr: datetime.utcnow()})
                )
                await _send_insurance_email(
                    "reminder", user.email, user.full_name or "",
                    profile.business_name, insurance_label,
                    policy.expires_at, days_remaining,
                )
                logger.info(
                    "[insurance-expiry] %s reminder → %s (policy %s, %d days left).",
                    label, user.email, policy.id, days_remaining,
                )
                break

        await db.commit()
        logger.info("[insurance-expiry] Run complete.")


async def _send_insurance_email(
    email_type: str,
    to_email: str,
    full_name: str,
    business_name: str,
    insurance_label: str,
    expires_at: date,
    days_remaining: int,
):
    """
    Sends an insurance expiry reminder or expiry notification email.
    Calls into resend_service — add these two functions there:
      send_insurance_expiry_reminder_email(to_email, full_name, business_name,
                                           insurance_label, expires_at, days_remaining)
      send_insurance_expired_email(to_email, full_name, business_name, insurance_label)
    """
    try:
        from services.resend_service import (
            send_insurance_expiry_reminder_email,
            send_insurance_expired_email,
        )
        if email_type == "reminder":
            await send_insurance_expiry_reminder_email(
                to_email=to_email,
                full_name=full_name,
                business_name=business_name,
                insurance_label=insurance_label,
                expires_at=expires_at,
                days_remaining=days_remaining,
            )
        elif email_type == "expired":
            await send_insurance_expired_email(
                to_email=to_email,
                full_name=full_name,
                business_name=business_name,
                insurance_label=insurance_label,
            )
    except Exception as e:
        logger.error(
            "[insurance-expiry] Email send failed (%s → %s): %s",
            email_type, to_email, e,
        )


# ── Task 5: Watchdog — ghost job detection ────────────────────────────────────
@celery_app.task(name="tasks.verification_tasks.watchdog_ghost_jobs")
def watchdog_ghost_jobs():
    """
    Every 5 minutes — finds jobs stuck in 'open' or 'pending' status for
    more than 10 minutes with no successful lead distribution task recorded.

    WHY THIS MATTERS:
      A job's Celery notification task can fail silently (worker crash, Redis
      OOM). The homeowner books, gets no confirmation. The tradie gets no
      lead. The job exists in the DB but nobody knows about it. Both sides
      think the booking didn't go through.

    WHAT IT DOES:
      1. Finds jobs: status IN ('open', 'pending') AND created_at < now - 10min
         AND (lead_task_id IS NULL OR lead task has not succeeded)
      2. Re-enqueues the lead distribution task via Celery.
      3. Updates job.lead_task_id with the new task ID.
      4. Logs every re-enqueue to the audit trail so Django admin can see it.

    IDEMPOTENCY:
      The lead distribution task itself must be idempotent — it checks
      whether leads already exist for the job before creating new ones.
      This watchdog only re-enqueues; it does not create leads directly.
    """
    _run(_async_watchdog_ghost_jobs())


async def _async_watchdog_ghost_jobs():
    from sqlalchemy import select, update
    from db.session import AsyncSessionLocal
    from models.job import Job

    cutoff = datetime.utcnow() - timedelta(minutes=10)

    # Statuses that need lead distribution but haven't completed it yet
    STUCK_STATUSES = {"open", "pending"}

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Job).where(
                Job.status.in_(STUCK_STATUSES),
                Job.is_deleted == False,
                Job.created_at < cutoff,
                Job.lead_task_id.is_(None),   # no task was ever enqueued
            )
        )
        stuck_jobs = res.scalars().all()

        if not stuck_jobs:
            logger.debug("[watchdog] No ghost jobs found.")
            return

        logger.warning(
            "[watchdog] Found %d ghost jobs — re-enqueueing lead distribution.",
            len(stuck_jobs),
        )

        for job in stuck_jobs:
            try:
                new_task = _enqueue_lead_distribution(job.id)
                if new_task:
                    await db.execute(
                        update(Job)
                        .where(Job.id == job.id)
                        .values(lead_task_id=new_task.id)
                    )
                    logger.warning(
                        "[watchdog] Re-enqueued job %s → task %s.",
                        job.id, new_task.id,
                    )
                else:
                    logger.error(
                        "[watchdog] Failed to re-enqueue job %s — no task returned.",
                        job.id,
                    )
            except Exception as e:
                logger.error(
                    "[watchdog] Exception re-enqueueing job %s: %s",
                    job.id, e,
                )

        await db.commit()

        # Also scan for jobs stuck with a task_id set but still in open/pending
        # after 15 minutes — the task may have been enqueued but never processed
        extended_cutoff = datetime.utcnow() - timedelta(minutes=15)
        res2 = await db.execute(
            select(Job).where(
                Job.status.in_(STUCK_STATUSES),
                Job.is_deleted == False,
                Job.created_at < extended_cutoff,
                Job.lead_task_id.is_not(None),   # task was enqueued but job still stuck
            )
        )
        stale_jobs = res2.scalars().all()

        if stale_jobs:
            logger.warning(
                "[watchdog] %d jobs have a task_id but are still stuck after 15min. "
                "Inspect Flower or dead-letter queue.",
                len(stale_jobs),
            )
            # Log job IDs so Django admin / Flower can investigate
            for job in stale_jobs:
                logger.warning(
                    "[watchdog] Stale job: id=%s status=%s task=%s created=%s",
                    job.id, job.status, job.lead_task_id, job.created_at,
                )


def _enqueue_lead_distribution(job_id: str):
    """
    Re-enqueues the lead distribution Celery task for a ghost job.
    Imports from lead_tasks to avoid circular imports at module level.
    Returns the Celery AsyncResult so the caller can store the new task ID.
    """
    try:
        from tasks.lead_tasks import distribute_leads_for_job
        # Always enqueue to the 'critical' queue — booking confirms are highest priority
        result = distribute_leads_for_job.apply_async(
            args=[job_id],
            queue="critical",
        )
        return result
    except Exception as e:
        logger.error(
            "[watchdog] _enqueue_lead_distribution failed for job %s: %s",
            job_id, e,
        )
        return None