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
from sqlalchemy import select

from models.user import User
from models.category import Category
from models.job import Job
from models.job_photo import JobPhoto
from models.lead import Lead
from models.quote import Quote
from models.review import Review
from models.tradie_profile import TradieProfile
from models.tradie_category import TradieCategory
from models.tradie_certification import TradieCertification, CertificationStatus
from models.insurance_policy import InsurancePolicy, InsuranceStatus, InsuranceType
from models.tradie_preference import TradiePreference
from models.tradie_pass import TradiePass
from services.category_resolver import canonical_trade_category

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


def _required_documents_for_category(category: Category | None) -> set[str]:
    """
    Backend mirror of frontend/src/lib/tradie-verification.ts.
    Keep this conservative: every returned document must be satisfied before
    production lead distribution can send work in that service.
    """
    if not category:
        return {"abn", "public_liability"}

    slug = (category.slug or "").lower().strip()
    name = (category.name or "").lower().strip()
    key = slug or name.replace(" ", "-")

    basic = {"cleaning", "handyman"}
    standard_insurance = {
        "painting", "plastering", "flooring", "tiling", "landscaping",
        "glazing", "pest-control",
    }
    site_safety = {"carpentry", "concreting", "fencing"}
    high_risk = {"roofing", "solar", "solar-installation", "demolition", "building", "bathroom-renovation"}
    strict = {
        "electrical", "electrician", "plumbing", "plumber", "gas-fitting", "gas-fitter",
        "hvac", "air-conditioning", "air-conditioner", "security", "waterproofing",
        "kitchen-renovation",
    }

    if key in basic:
        return {"abn"}
    if key in standard_insurance:
        return {"abn", "public_liability"}
    if key in site_safety:
        return {"abn", "public_liability", "white_card"}
    if key in high_risk:
        return {"abn", "public_liability", "trade_licence", "white_card", "swms"}
    if key in strict or any(p in name for p in ("electric", "plumb", "gas", "solar", "building", "demolition", "waterproof", "roof", "security", "air condition", "hvac", "refriger")):
        return {"abn", "public_liability", "trade_licence", "white_card"}

    return {"abn", "public_liability"}


async def _tradie_satisfies_service_docs(db, profile: TradieProfile, category: Category | None) -> tuple[bool, list[str]]:
    required = _required_documents_for_category(category)
    missing: list[str] = []

    pass_res = await db.execute(select(TradiePass).where(TradiePass.tradie_id == profile.id))
    tradie_pass = pass_res.scalar_one_or_none()

    if "abn" in required:
        has_abn = profile.verification_status == "verified" or bool(tradie_pass and tradie_pass.abn_verified)
        if not has_abn:
            missing.append("abn")

    if "public_liability" in required:
        ins_res = await db.execute(
            select(InsurancePolicy.id).where(
                InsurancePolicy.tradie_profile_id == profile.id,
                InsurancePolicy.insurance_type == InsuranceType.PUBLIC_LIABILITY,
                InsurancePolicy.status == InsuranceStatus.VERIFIED,
            ).limit(1)
        )
        if not ins_res.scalar_one_or_none():
            missing.append("public_liability")

    if "trade_licence" in required:
        category_id = category.id if category else None
        cert_res = await db.execute(
            select(TradieCertification.category_id).where(
                TradieCertification.tradie_profile_id == profile.id,
                TradieCertification.status == CertificationStatus.VERIFIED,
            )
        )
        cert_category_ids = set(cert_res.scalars().all())
        has_matching_cert = category_id in cert_category_ids

        if not has_matching_cert and category_id:
            cert_categories_res = await db.execute(
                select(Category).where(Category.id.in_(cert_category_ids))
            )
            for cert_category in cert_categories_res.scalars().all():
                canonical = await canonical_trade_category(db, cert_category)
                if canonical and canonical.id == category_id:
                    has_matching_cert = True
                    break

        if not has_matching_cert:
            missing.append("trade_licence")

    if "white_card" in required:
        has_white_card = bool(
            tradie_pass and (
                getattr(tradie_pass, "white_card_verified", False)
                or getattr(tradie_pass, "wc_verified", False)
            )
        )
        if not has_white_card:
            missing.append("white_card")

    if "swms" in required:
        if not bool(tradie_pass and tradie_pass.swms_uploaded):
            missing.append("swms")

    return len(missing) == 0, missing


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

        # 2. Idempotency guard — only skip if we already found at least 1 lead.
        #    If previous run found 0 leads (no tradies matched), allow retry so that
        #    newly-onboarded tradies or tradies who just turned on availability can be matched.
        if job.match_intelligence:
            try:
                mi = json.loads(job.match_intelligence)
                if mi.get("matched", 0) > 0:
                    print(f"[leads] Job {job_id} already has {mi['matched']} lead(s) — skip")
                    return
                print(f"[leads] Job {job_id} had 0 leads before — retrying distribution")
            except Exception:
                pass

        # Geocoding is non-fatal — fall back to suburb-name-only matching
        has_coords = bool(job.lat and job.lng)
        if not has_coords:
            print(f"[leads] Job {job_id} has no coordinates — matching by suburb name only")

        print(f"[leads] ─────────────────────────────────────────────────")
        print(f"[leads] JOB: {job.title} | {job.suburb}, {job.state}")
        if has_coords:
            print(f"[leads]   Coords: ({job.lat:.4f}, {job.lng:.4f})")
        print(f"[leads]   Category: {job.category_id}")

        cat_res = await db.execute(select(Category).where(Category.id == job.category_id))
        job_category = cat_res.scalar_one_or_none()
        canonical_category = await canonical_trade_category(db, job_category) if job_category else None
        if canonical_category and canonical_category.id != job.category_id:
            print(f"[leads]   Normalising job category {job.category_id} -> {canonical_category.id} ({canonical_category.name})")
            job.category_id = canonical_category.id
            job_category = canonical_category
            db.add(job)

        child_res = await db.execute(select(Category.id).where(Category.parent_id == job.category_id))
        child_ids = [row[0] for row in child_res.all()]
        grandchild_ids = []
        if child_ids:
            grandchild_res = await db.execute(select(Category.id).where(Category.parent_id.in_(child_ids)))
            grandchild_ids = [row[0] for row in grandchild_res.all()]
        match_category_ids = [job.category_id, *child_ids, *grandchild_ids]

        # 3. SQL filter — in DEV mode we relax approval + geocoding requirements
        #    so that test tradies receive leads without going through full verification.
        IS_DEV = os.getenv("ENVIRONMENT", "development") == "development"

        base_filters = [
            TradieCategory.category_id.in_(match_category_ids),
            TradieProfile.is_available == True,
            User.is_active == True,
        ]
        if IS_DEV:
            # Dev: accept any tradie that has a profile and is active
            print(f"[leads]   DEV mode — skipping verification_status/lat/lng/is_verified filters")
        else:
            # Production: strict — only verified, geocoded tradies
            # Django admin sets verification_status="verified" (NOT "approved")
            base_filters += [
                TradieProfile.verification_status == "verified",
                TradieProfile.lat.is_not(None),
                TradieProfile.lng.is_not(None),
                User.is_verified == True,
            ]

        candidates_q = (
            select(TradieProfile, User, TradiePreference)
            .join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id)
            .join(User, User.id == TradieProfile.user_id)
            .outerjoin(TradiePreference, TradiePreference.tradie_id == TradieProfile.id)
            .where(*base_filters)
        )
        result = await db.execute(candidates_q)
        rows = result.all()

        if not IS_DEV:
            doc_eligible_rows = []
            for profile, user, pref in rows:
                ok, missing = await _tradie_satisfies_service_docs(db, profile, job_category)
                if ok:
                    doc_eligible_rows.append((profile, user, pref))
                else:
                    print(
                        f"[leads]   Skip {profile.business_name}: "
                        f"missing verified docs for {job_category.name if job_category else 'service'} "
                        f"({', '.join(missing)})"
                    )
            rows = doc_eligible_rows

        print(f"[leads]   Eligible tradies (sql): {len(rows)}")

        if not rows:
            print(f"[leads]   0 tradies — trying NLP title/description fallback...")

            # ── Safety net: the job's category_id may be wrong (phantom UUID created
            #    by an old bug, or incorrectly resolved before the category fix was
            #    deployed). Re-resolve the correct canonical trade category using the
            #    job's title and description via the same NLP resolver the booking
            #    wizard uses. This is far more accurate than a slug CONTAINS query.
            from services.category_resolver import resolve_trade_category as _resolve

            search_text = " ".join(
                part for part in [job.title or "", job.description or ""] if part
            ).strip()

            real_category = None
            if search_text:
                real_category = await _resolve(db, search_text)

            if real_category and real_category.id != job.category_id:
                print(
                    f"[leads]   NLP remap: {job.category_id} → "
                    f"{real_category.id} ({real_category.name}) "
                    f"[matched from: '{search_text[:60]}']"
                )
                job.category_id = real_category.id
                db.add(job)

                # Rebuild the child/grandchild id list for the remapped category
                child_res2 = await db.execute(
                    select(Category.id).where(Category.parent_id == real_category.id)
                )
                child_ids2 = [r[0] for r in child_res2.all()]
                grandchild_ids2: list[str] = []
                if child_ids2:
                    gc_res2 = await db.execute(
                        select(Category.id).where(Category.parent_id.in_(child_ids2))
                    )
                    grandchild_ids2 = [r[0] for r in gc_res2.all()]
                remap_ids = [real_category.id, *child_ids2, *grandchild_ids2]

                new_filters = base_filters.copy()
                new_filters[0] = TradieCategory.category_id.in_(remap_ids)
                retry_q = (
                    select(TradieProfile, User, TradiePreference)
                    .join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id)
                    .join(User, User.id == TradieProfile.user_id)
                    .outerjoin(TradiePreference, TradiePreference.tradie_id == TradieProfile.id)
                    .where(*new_filters)
                )
                retry_result = await db.execute(retry_q)
                rows = retry_result.all()

                if not IS_DEV:
                    doc_eligible_rows = []
                    for profile, user, pref in rows:
                        ok, missing = await _tradie_satisfies_service_docs(db, profile, real_category)
                        if ok:
                            doc_eligible_rows.append((profile, user, pref))
                        else:
                            print(
                                f"[leads]   Skip {profile.business_name}: "
                                f"missing verified docs for {real_category.name} "
                                f"({', '.join(missing)})"
                            )
                    rows = doc_eligible_rows

                print(f"[leads]   After NLP remap — eligible tradies: {len(rows)}")
            else:
                if not search_text:
                    print(f"[leads]   No title/description to resolve from")
                elif not real_category:
                    print(f"[leads]   NLP could not resolve a category from: '{search_text[:60]}'")
                else:
                    print(f"[leads]   NLP resolved same category — no change")

            if not rows:
                print(f"[leads]   0 tradies even after fallback — notifying homeowner")
                await _store_match_intelligence(db, job, 0, 0)
                await _notify_homeowner_no_tradies(db, job)
                await db.commit()
                return

        # 4. Geo filter — gracefully handle missing coordinates on job or tradie
        in_range, out_of_range = [], []
        for profile, user, pref in rows:
            suburb_match = _suburb_in_list(job.suburb, pref.service_suburbs if pref else None)

            if has_coords and profile.lat and profile.lng:
                dist = haversine_distance(job.lat, job.lng, profile.lat, profile.lng)
                in_radius = dist <= (profile.radius_km or 25)
            else:
                # No coordinates available — include everyone (suburb match is a bonus)
                dist = 0.0
                in_radius = True

            if in_radius or suburb_match:
                print(f"[leads]   ✓ {profile.business_name} ({dist:.1f}km)")
                in_range.append((dist, profile))
            else:
                out_of_range.append((dist, profile))
                print(f"[leads]   ✗ {profile.business_name} ({dist:.1f}km, out of range)")

        # 5. Expand radius 1.5× if < 3 found (only meaningful when coords exist)
        if len(in_range) < 3 and out_of_range and has_coords:
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

        # 6. Create leads (skip duplicates) and collect new ones for notification
        leads_created = 0
        new_lead_profiles = []   # (profile, user) for email notifications
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
            new_lead_profiles.append(profile)

        await _store_match_intelligence(db, job, leads_created, len(in_range))

        # ── Transition job from "open" → "quoted" now that tradies are notified ──
        # This is the system-level transition that unlocks homeowner accept flow.
        # We do this directly (not via the state machine) so it works even before
        # the job_events table migration has been applied.
        if job.status == "open":
            job.status = "quoted"
            db.add(job)
            print(f"[leads]   Job status: open → quoted")

        await db.commit()
        print(f"[leads] DONE — {leads_created} lead(s) for {job_id}")

        # 7. Email each tradie about the new lead (best-effort, non-fatal)
        if new_lead_profiles:
            await _notify_tradies_new_lead(db, job, new_lead_profiles)

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


async def _notify_tradies_new_lead(db, job, profiles: list) -> None:
    """
    Email each tradie when they receive a new lead.
    This is the primary trigger that brings tradies into their dashboard.
    """
    try:
        from sqlalchemy import select
        from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME

        urgency_map = {
            "emergency":      ("🚨 URGENT", "#A33030"),
            "asap":           ("⚡ ASAP",    "#B85C00"),
            "next_few_days":  ("📅 This week", "#0077AA"),
            "next_few_weeks": ("🗓 This month", "#5B7560"),
            "flexible":       ("🌿 Flexible",  "#5B7560"),
        }
        urgency_label, urgency_color = urgency_map.get(
            job.urgency or "flexible", ("📅 New job", "#0077AA")
        )

        for profile in profiles:
            try:
                user_res = await db.execute(
                    select(User).where(User.id == profile.user_id)
                )
                tradie_user = user_res.scalar_one_or_none()
                if not tradie_user or not tradie_user.email:
                    continue

                name = _first(tradie_user.full_name or profile.business_name or "")
                body = f"""
                  <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                             font-weight:500;color:#1A1A1A;">New job lead for you!</h1>
                  <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
                    G'day {name}, a new job has been posted in your area and you've been matched.
                    Log in quickly — leads are sent to up to 3 tradies and the homeowner picks one.
                  </p>
                  <div style="background:#F8F5EE;border:1px solid #E6D9B5;border-radius:16px;
                              padding:20px 24px;margin:0 0 20px;">
                    <p style="margin:0 0 4px;font-size:11px;font-weight:700;
                              color:{urgency_color};text-transform:uppercase;letter-spacing:.08em;">
                      {urgency_label}
                    </p>
                    <p style="margin:0 0 8px;font-size:20px;font-weight:800;color:#1A1A1A;">
                      {job.title or "New job"}
                    </p>
                    <p style="margin:0;font-size:13.5px;color:#4A4A48;">
                      📍 {job.suburb or "Location TBC"}{', ' + job.state if job.state else ''}
                    </p>
                  </div>
                  <p style="margin:0 0 20px;font-size:13px;color:#8A8882;">
                    View the full job details, photos and quote from your dashboard.
                    Don't delay — tradies who respond quickly win more jobs.
                  </p>
                  {_btn("View Lead & Quote", "http://localhost:3000/tradie/dashboard", "#A68A4E")}
                  <p style="margin:24px 0 0;font-size:12px;color:#B8B5AE;text-align:center;">
                    You received this because you are listed as a {profile.business_name or 'tradie'}
                    in the {job.suburb or 'local'} area.
                  </p>"""
                text = (
                    f"G'day {name},\n\n"
                    f"New job: {job.title or 'New job'} in {job.suburb or 'your area'}.\n\n"
                    f"Log in to view and quote: http://localhost:3000/tradie/dashboard\n\n"
                    f"— The {APP_NAME} team"
                )
                await _send_raw_email(
                    tradie_user.email,
                    f"⚡ New lead: {job.title or 'New job'} — {job.suburb or 'your area'}",
                    _base_html(body, "#A68A4E"),
                    text,
                )
                print(f"[leads]   → Email sent to {tradie_user.email}")
            except Exception as e:
                print(f"[leads]   Warning: email to tradie {profile.id} failed: {e}")
    except Exception as e:
        print(f"[leads]   Warning: tradie notifications failed: {e}")


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
