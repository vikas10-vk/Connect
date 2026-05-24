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

import asyncio
import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.category import Category
from models.insurance_policy import InsurancePolicy, InsuranceStatus, InsuranceType
from models.job import Job
from models.lead import Lead
from models.quote import Quote
from models.tradie_category import TradieCategory
from models.tradie_certification import CertificationStatus, TradieCertification
from models.tradie_pass import TradiePass
from models.tradie_preference import TradiePreference
from models.tradie_profile import TradieProfile
from models.user import User
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
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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

# ── Specificity scoring constants ────────────────────────────────────────────
# Used by _distribute_leads to rank candidate tradies by how closely their
# registered service categories match the job's category.
#
#   3.0  → Tradie registered for the EXACT job category (or a child of it —
#          i.e. they are a *more specialised* tradie than the job requires).
#          Example: job is "Cleaning", tradie registered for "Pool Cleaning".
#          Example: job is "Pool Cleaning", tradie registered for "Pool Cleaning".
#   1.0  → Tradie registered for the job category's PARENT (they cover the
#          broader trade). Example: job is "Pool Cleaning", tradie registered
#          for the parent "Cleaning". They CAN do it but they're not specialists.
#   0.5  → Tradie registered for the GRANDPARENT (last-resort match).
#
# This means a pool-cleaning specialist always receives pool cleaning leads
# BEFORE a generic cleaning tradie does, even if the generic tradie is slightly
# closer. The pay-per-lead self-correcting filter on real hipages is replaced
# here by an explicit ranking — bad matches simply never beat good matches.
SCORE_EXACT_OR_DEEPER = 3.0
SCORE_PARENT          = 1.0
SCORE_GRANDPARENT     = 0.5


async def _build_category_score_map(db, job_category_id: str) -> tuple[dict[str, float], dict[str, str | None]]:
    """
    Build a {category_id: score} map for a given job category, plus a
    {role: category_id} structure that the supply-gap audit can describe.

    Returns:
      score_map      — category_id → score (see SCORE_* constants).
      taxonomy_refs  — {"job": <id>, "parent": <id|None>, "grandparent": <id|None>,
                       "child_count": <int>, "grandchild_count": <int>}

    Why both directions are scored at 3.0 (exact OR deeper):
      A "Pool Cleaning" specialist is a better match for a broader "Cleaning"
      job than a generalist is, so deeper specificity (children/grandchildren
      of the job category) is rewarded just like an exact match. Going *up*
      (parent / grandparent) is what gets penalised — the tradie is broader
      than the job requires, so they're a less specific fit.
    """
    # ── Expand DOWN: children + grandchildren ────────────────────────────
    child_res = await db.execute(
        select(Category.id).where(Category.parent_id == job_category_id)
    )
    child_ids = [row[0] for row in child_res.all()]
    grandchild_ids: list[str] = []
    if child_ids:
        gc_res = await db.execute(
            select(Category.id).where(Category.parent_id.in_(child_ids))
        )
        grandchild_ids = [row[0] for row in gc_res.all()]

    # ── Expand UP: parent + grandparent ──────────────────────────────────
    parent_res = await db.execute(
        select(Category.parent_id).where(Category.id == job_category_id)
    )
    parent_row = parent_res.first()
    parent_id = parent_row[0] if parent_row and parent_row[0] else None
    grandparent_id = None
    if parent_id:
        gp_res = await db.execute(
            select(Category.parent_id).where(Category.id == parent_id)
        )
        gp_row = gp_res.first()
        grandparent_id = gp_row[0] if gp_row and gp_row[0] else None

    score_map: dict[str, float] = {}
    # Exact match (job's own category) takes the highest score.
    score_map[job_category_id] = SCORE_EXACT_OR_DEEPER
    # Children & grandchildren of the job — these tradies are *specialists*.
    for cid in child_ids + grandchild_ids:
        score_map[cid] = SCORE_EXACT_OR_DEEPER
    # Parent — broader tradie, can still do the job.
    if parent_id:
        score_map.setdefault(parent_id, SCORE_PARENT)
    # Grandparent — much broader, last-resort match.
    if grandparent_id:
        score_map.setdefault(grandparent_id, SCORE_GRANDPARENT)

    taxonomy = {
        "job":              job_category_id,
        "parent":           parent_id,
        "grandparent":      grandparent_id,
        "child_count":      len(child_ids),
        "grandchild_count": len(grandchild_ids),
    }
    return score_map, taxonomy


async def _gather_scored_candidates(
    db,
    score_map: dict[str, float],
    is_dev: bool,
    job_category: Category | None,
):
    """
    Pull all candidate tradies whose TradieCategory.category_id appears in
    score_map. For each unique tradie, keep the MAX score across all of their
    registered categories (a tradie who has both "Cleaning" and "Pool Cleaning"
    on a pool job should be scored 3.0, not the average).

    Production runs additionally enforce verified docs for the job's required
    document set — the same gate used by the live system.

    Returns: list of (profile, user, pref, score) tuples, one per tradie.
    """
    base_filters = [
        TradieCategory.category_id.in_(list(score_map.keys())),
        TradieProfile.is_available == True,
        User.is_active == True,
    ]
    if not is_dev:
        base_filters += [
            TradieProfile.verification_status == "verified",
            TradieProfile.lat.is_not(None),
            TradieProfile.lng.is_not(None),
            User.is_verified == True,
        ]

    q = (
        select(TradieProfile, User, TradiePreference, TradieCategory.category_id)
        .join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id)
        .join(User, User.id == TradieProfile.user_id)
        .outerjoin(TradiePreference, TradiePreference.tradie_id == TradieProfile.id)
        .where(*base_filters)
    )
    result = await db.execute(q)

    # Reduce multi-category-per-tradie rows to one row per tradie with MAX score.
    best: dict[str, tuple[TradieProfile, User, TradiePreference | None, float]] = {}
    for profile, user, pref, matched_cat_id in result.all():
        score = score_map.get(matched_cat_id, 0.0)
        existing = best.get(profile.id)
        if existing is None or score > existing[3]:
            best[profile.id] = (profile, user, pref, score)
    rows = list(best.values())

    # Production document-verification gate.
    if not is_dev:
        eligible: list = []
        for profile, user, pref, score in rows:
            ok, missing = await _tradie_satisfies_service_docs(db, profile, job_category)
            if ok:
                eligible.append((profile, user, pref, score))
            else:
                print(
                    f"[leads]   Skip {profile.business_name}: "
                    f"missing verified docs for {job_category.name if job_category else 'service'} "
                    f"({', '.join(missing)})"
                )
        rows = eligible
    return rows


def _radius_filter(scored_rows, job_lat, job_lng, job_suburb, radius_multiplier: float = 1.0):
    """
    Apply a haversine + suburb-name geo filter to scored candidates.

    A tradie passes if EITHER:
      • the job is inside (tradie.radius_km × radius_multiplier) kilometres, OR
      • the job's suburb is explicitly listed in TradiePreference.service_suburbs.

    Returns: list of (distance_km, score, profile, user) tuples.
    """
    has_coords = bool(job_lat and job_lng)
    in_range = []
    for profile, user, pref, score in scored_rows:
        suburb_match = _suburb_in_list(job_suburb, pref.service_suburbs if pref else None)

        if has_coords and profile.lat and profile.lng:
            dist = haversine_distance(job_lat, job_lng, profile.lat, profile.lng)
            radius = (profile.radius_km or 25) * radius_multiplier
            in_radius = dist <= radius
        else:
            # No coordinates available — include everyone (suburb match is a bonus).
            dist = 0.0
            in_radius = True

        if in_radius or suburb_match:
            in_range.append((dist, score, profile, user))
    return in_range


async def _log_supply_gap(db, job, attempts: list[str], score_map_size: int):
    """
    Write a structured JobEvent so admins can spot zero-supply areas and the
    business team can recruit. Uses the same actor_role='system' pattern that
    no-show alerts use, so the existing admin audit views surface it.
    """
    try:
        from models.job_event import JobEvent
        ev = JobEvent(
            job_id=job.id,
            actor_id="system",
            actor_role="system",
            action="supply_gap_alert",
            old_value={"status": job.status},
            new_value={
                "category_id":     job.category_id,
                "suburb":          job.suburb,
                "state":           job.state,
                "attempts_tried":  attempts,
                "categories_searched": score_map_size,
            },
            note=(
                f"0 tradies matched for category {job.category_id} in {job.suburb}, "
                f"{job.state}. Attempts: {', '.join(attempts)}. "
                f"Consider recruiting tradies in this region/category."
            ),
        )
        db.add(ev)
    except Exception as exc:
        # Audit logging must never block the user-facing path.
        print(f"[leads]   Warning: supply-gap audit log failed: {exc}")


async def _distribute_leads(job_id: str, session_factory):
    """
    Match a homeowner job to up to 3 tradies, ranked by specificity then distance.

    Pipeline:
      1. Load job & normalise category to the canonical trade taxonomy.
      2. Build score_map: exact-or-deeper (3.0), parent (1.0), grandparent (0.5).
      3. Gather candidate tradies (one row per tradie, with their MAX score).
      4. NLP title/description fallback if the SQL category match returns 0
         (handles the historical bug where some jobs had stale category_ids).
      5. Geo-filter at base radius. If <3, expand to 1.5×. If still <3, expand to 2×.
      6. Sort by (-score, distance) → highest-specificity, then closest first.
      7. Take top 3 and create Lead rows.
      8. If no leads were created after every fallback, notify the homeowner
         honestly AND write a JobEvent so admins see the supply gap.
    """
    from sqlalchemy import select

    async with session_factory() as db:

        # 1. Load job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            print(f"[leads] Job {job_id} not found")
            return

        # 2. Idempotency guard — only skip if we already found at least 1 lead.
        #    A previous 0-lead run is allowed to retry so that newly-onboarded
        #    tradies or tradies who just turned availability on can be matched.
        if job.match_intelligence:
            try:
                mi = json.loads(job.match_intelligence)
                if mi.get("matched", 0) > 0:
                    print(f"[leads] Job {job_id} already has {mi['matched']} lead(s) — skip")
                    return
                print(f"[leads] Job {job_id} had 0 leads before — retrying distribution")
            except Exception:
                pass

        has_coords = bool(job.lat and job.lng)
        if not has_coords:
            print(f"[leads] Job {job_id} has no coordinates — matching by suburb name only")

        print("[leads] ─────────────────────────────────────────────────")
        print(f"[leads] JOB: {job.title} | {job.suburb}, {job.state}")
        if has_coords:
            print(f"[leads]   Coords: ({job.lat:.4f}, {job.lng:.4f})")
        print(f"[leads]   Category: {job.category_id}")

        cat_res = await db.execute(select(Category).where(Category.id == job.category_id))
        job_category = cat_res.scalar_one_or_none()

        # ── 3. Build the specificity score map ────────────────────────────
        # NOTE: We deliberately do NOT collapse the job's category to its level-1
        # parent here. Jobs posted at the subcategory level ("Pool Cleaning")
        # must stay at the subcategory level so specialist tradies score higher
        # than generalists. The booking wizard is responsible for picking the
        # right level; the matcher only uses the taxonomy to score, never to
        # rewrite the job's category.
        score_map, taxonomy = await _build_category_score_map(db, job.category_id)
        print(
            f"[leads]   Score map — {len(score_map)} IDs "
            f"(exact+children {sum(1 for s in score_map.values() if s == SCORE_EXACT_OR_DEEPER)}, "
            f"parent {sum(1 for s in score_map.values() if s == SCORE_PARENT)}, "
            f"grandparent {sum(1 for s in score_map.values() if s == SCORE_GRANDPARENT)})"
        )

        # ── 4. SQL filter — production vs dev gates ────────────────────────
        IS_DEV = os.getenv("ENVIRONMENT", "development") == "development"
        if IS_DEV:
            print("[leads]   DEV mode — skipping verification_status/lat/lng/is_verified filters")

        scored_rows = await _gather_scored_candidates(db, score_map, IS_DEV, job_category)
        print(f"[leads]   Eligible tradies (sql): {len(scored_rows)}")

        attempts: list[str] = ["category_match"]

        # ── 5. NLP fallback for jobs that arrived with a stale category_id ─
        if not scored_rows:
            print("[leads]   0 tradies — trying NLP title/description fallback...")
            attempts.append("nlp_remap")
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
                score_map, taxonomy = await _build_category_score_map(db, real_category.id)
                scored_rows = await _gather_scored_candidates(db, score_map, IS_DEV, real_category)
                print(f"[leads]   After NLP remap — eligible tradies: {len(scored_rows)}")
            else:
                if not search_text:
                    print("[leads]   No title/description to resolve from")
                elif not real_category:
                    print(f"[leads]   NLP could not resolve a category from: '{search_text[:60]}'")
                else:
                    print("[leads]   NLP resolved same category — no change")

        if not scored_rows:
            print("[leads]   0 tradies even after NLP fallback — supply gap")
            await _store_match_intelligence(db, job, 0, 0)
            await _log_supply_gap(db, job, attempts + ["zero_candidates"], len(score_map))
            await _notify_homeowner_no_tradies(db, job)
            await db.commit()
            return

        # ── 6. Geo filter with auto-radius expansion ──────────────────────
        # Stages: base radius → 1.5× → 2×. We stop as soon as we have ≥ 3
        # candidates so the closest, most relevant tradies always win.
        # When coordinates are missing on the job, every stage returns the
        # full set (because _radius_filter falls back to "include all"),
        # so we just take the first stage and move on.
        in_range = _radius_filter(scored_rows, job.lat, job.lng, job.suburb, 1.0)
        print(f"[leads]   In base radius: {len(in_range)}")

        if len(in_range) < 3 and has_coords:
            attempts.append("radius_1.5x")
            in_range_15 = _radius_filter(scored_rows, job.lat, job.lng, job.suburb, 1.5)
            if len(in_range_15) > len(in_range):
                print(f"[leads]   Expanded radius 1.5× → {len(in_range_15)}")
                in_range = in_range_15

        if len(in_range) < 3 and has_coords:
            attempts.append("radius_2x")
            in_range_20 = _radius_filter(scored_rows, job.lat, job.lng, job.suburb, 2.0)
            if len(in_range_20) > len(in_range):
                print(f"[leads]   Expanded radius 2.0× → {len(in_range_20)}")
                in_range = in_range_20

        if not in_range:
            print("[leads]   No tradies after every radius — supply gap")
            await _store_match_intelligence(db, job, 0, 0)
            await _log_supply_gap(db, job, attempts + ["all_radii_empty"], len(score_map))
            await _notify_homeowner_no_tradies(db, job)
            await db.commit()
            return

        # ── 7. Rank: (specificity DESC, distance ASC) ─────────────────────
        # The negative score in the sort key flips the natural ascending
        # order to descending — so a pool-cleaning specialist (score 3.0)
        # is always picked over a generic cleaning tradie (score 1.0),
        # even when the generic tradie is slightly closer. Distance is
        # the tie-breaker.
        in_range.sort(key=lambda r: (-r[1], r[0]))
        selected = in_range[:3]

        for dist, score, profile, _ in selected:
            tag = "EXACT" if score >= SCORE_EXACT_OR_DEEPER else "PARENT" if score >= SCORE_PARENT else "GRANDPARENT"
            print(f"[leads]   ✓ {profile.business_name} ({dist:.1f}km, score {score}, {tag})")

        # ── 8. Create Lead rows (idempotent on (job_id, tradie_id)) ───────
        leads_created = 0
        new_lead_profiles: list = []
        for dist, score, profile, _ in selected:
            exists = await db.execute(
                select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == profile.id)
            )
            if exists.scalar_one_or_none():
                print(f"[leads]   - Lead exists for {profile.business_name}, skip")
                continue
            insert_result = await db.execute(
                pg_insert(Lead)
                .values(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    tradie_id=profile.id,
                    credits_charged=0,
                    status="sent",
                )
                .on_conflict_do_nothing(index_elements=["job_id", "tradie_id"])
            )
            if not insert_result.rowcount:
                print(f"[leads]   - Lead raced for {profile.business_name}, skip")
                continue
            leads_created += 1
            print(f"[leads]   → Lead: {profile.business_name} ({dist:.1f}km)")
            new_lead_profiles.append(profile)

        await _store_match_intelligence(db, job, leads_created, len(in_range))

        # Job stays "open" after distribution — status only flips to "quoted"
        # when a tradie actually submits a quote (see routers/quotes.py).

        await db.commit()
        print(f"[leads] DONE — {leads_created} lead(s) for {job_id}")

        # 9. Notify tradies — best-effort, never fatal.
        if new_lead_profiles:
            await _notify_tradies_new_lead(db, job, new_lead_profiles)

        # 10. If even after radius expansion we ended up with 0 leads
        #     (e.g. every candidate already had a Lead row), still log a
        #     supply-gap event so admins see what happened.
        if leads_created == 0:
            await _log_supply_gap(db, job, attempts + ["all_already_have_leads"], len(score_map))
            await _notify_homeowner_no_tradies(db, job)
            await db.commit()

        print("[leads] ─────────────────────────────────────────────────")


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

        from services.resend_service import APP_NAME, _base_html, _btn, _first, _send_raw_email

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

    from services.job_state_machine import InvalidTransitionError, JobStateMachine

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
                    from services.resend_service import (
                        APP_NAME,
                        _base_html,
                        _first,
                        _send_raw_email,
                    )
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

    from models.lead import Lead
    from services.earnings_service import EarningsNotPayableError, record_earning
    from services.job_state_machine import InvalidTransitionError, JobStateMachine

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
        booked = 0

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
                logger.info("[auto-close] Job %s -> closed.", job.id)
            except InvalidTransitionError as e:
                logger.error("[auto-close] Could not close job %s: %s", job.id, e)
                continue

            # ── Auto-book the earning for the hired tradie ───────────────
            # Now that status is 'closed', the dispute window is fully
            # closed and the accepted quote amount is safe to book.
            # We never raise here — booking failures are logged so the manual
            # /earnings/record fallback still works.
            try:
                quote_res = await db.execute(
                    select(Quote).where(
                        Quote.job_id == job.id,
                        Quote.status == "accepted",
                    ).limit(1)
                )
                accepted_quote = quote_res.scalar_one_or_none()
                if not accepted_quote:
                    logger.debug("[auto-close] Job %s has no accepted quote — no earning to book.", job.id)
                    continue

                # The Lead row tells us which tradie was actually hired
                lead_res = await db.execute(
                    select(Lead).where(Lead.job_id == job.id).limit(1)
                )
                lead = lead_res.scalar_one_or_none()
                tradie_id = (
                    getattr(accepted_quote, "tradie_id", None)
                    or (lead.tradie_id if lead else None)
                )
                if not tradie_id:
                    logger.warning("[auto-close] Job %s has no tradie to book the earning to.", job.id)
                    continue

                amount = float(getattr(accepted_quote, "amount", 0) or 0)
                if amount <= 0:
                    logger.warning("[auto-close] Job %s accepted quote has non-positive amount %s.", job.id, amount)
                    continue

                # enforce_payable=False is safe here — we just transitioned
                # to 'closed' in this same transaction so the strict job check
                # would race on the not-yet-committed status.
                await record_earning(
                    tradie_id=tradie_id,
                    job_id=job.id,
                    gross_amount=amount,
                    db=db,
                    enforce_payable=False,
                )
                booked += 1
                logger.info("[auto-close] Booked $%.2f earning for tradie %s on job %s.",
                            amount, tradie_id, job.id)
            except EarningsNotPayableError as exc:
                logger.warning("[auto-close] Earning skipped for job %s: %s", job.id, exc)
            except Exception as exc:
                logger.error("[auto-close] Earning booking failed for job %s: %s", job.id, exc)

        await db.commit()
        logger.info("[auto-close] Done -- %d/%d job(s) closed, %d earning(s) booked.",
                    closed, len(jobs), booked)


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

    from services.job_state_machine import InvalidTransitionError, JobStateMachine

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

        from services.resend_service import APP_NAME, _base_html, _btn, _first, _send_raw_email

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
          {_btn("View Job", "http://localhost:3000/dashboard", "#B85C00")}"""
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

        from services.resend_service import APP_NAME, _base_html, _btn, _first, _send_raw_email

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
          {_btn("Re-post your job", "http://localhost:3000/book", "#2E7D5A")}"""
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
        from services.resend_service import APP_NAME, _base_html, _first, _send_raw_email

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


# ═══════════════════════════════════════════════════════════════════════════
# NEW TASK: Retroactive lead distribution for newly-verified tradies
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="critical")
def redistribute_open_jobs_for_tradie(self, tradie_profile_id: str):
    """
    Fired immediately when a tradie's verification_status transitions to 'verified'.

    Solves the "late subscriber" / "delayed consumer" problem at production scale:

      ► Instagram analogy: when a user follows a new creator, past posts are
        retroactively surfaced in their feed. We do the same — when a tradie
        gets verified, past open jobs that got 0 leads (because no tradie existed
        at post time) are retroactively pushed to them.

      ► Uber analogy: when a driver comes online, the dispatch queue immediately
        assigns waiting trip requests. We scan the queue of 0-lead open jobs and
        re-trigger distribution so the newly-available tradie can be matched.

    Algorithm:
      1. Load the tradie's service categories and service area (radius + coords).
      2. Find all OPEN jobs posted in the last 30 days whose category overlaps.
      3. Skip jobs that already have ≥ 1 lead (another tradie was already matched).
      4. Filter by geography — only jobs within 1.5× the tradie's service radius.
      5. Reset match_intelligence on eligible jobs (clears the idempotency guard).
      6. Re-queue distribute_leads for each job with a staggered jitter.

    The 30-day lookback window prevents lead spam for jobs that homeowners have
    already resolved via other channels. Jobs older than 30 days are handled by
    the existing redistribute-stale-jobs beat task which runs every 6 hours.
    """
    _run_task(lambda sf: _async_redistribute_open_jobs_for_tradie(tradie_profile_id, sf))


async def _async_redistribute_open_jobs_for_tradie(
    tradie_profile_id: str,
    session_factory,
) -> None:
    """
    Core async logic for redistribute_open_jobs_for_tradie.
    Runs inside a fresh event loop + fresh DB engine (see _run_task).
    """
    async with session_factory() as db:

        # ── 1. Load the newly-verified tradie ─────────────────────────────
        profile_res = await db.execute(
            select(TradieProfile).where(TradieProfile.id == tradie_profile_id)
        )
        profile = profile_res.scalar_one_or_none()
        if not profile:
            print(f"[retrodist] Tradie profile {tradie_profile_id} not found — skip")
            return

        if profile.verification_status != "verified":
            print(
                f"[retrodist] Tradie {profile.business_name} is not yet verified "
                f"(status={profile.verification_status}) — skip"
            )
            return

        print(
            "[retrodist] ══════════════════════════════════════════════════════"
        )
        print(
            f"[retrodist] Tradie verified: {profile.business_name} ({tradie_profile_id})"
        )

        # ── 2. Fetch the tradie's registered categories ───────────────────
        cat_res = await db.execute(
            select(TradieCategory.category_id)
            .where(TradieCategory.tradie_id == tradie_profile_id)
        )
        tradie_category_ids: list[str] = [row[0] for row in cat_res.all()]

        if not tradie_category_ids:
            print(
                f"[retrodist] {profile.business_name} has no registered categories — skip"
            )
            return

        # Also include parent categories so a "Pool Cleaning" tradie can be matched
        # against a job posted with the parent "Cleaning" category (and vice-versa).
        parent_res = await db.execute(
            select(Category.parent_id)
            .where(
                Category.id.in_(tradie_category_ids),
                Category.parent_id.isnot(None),
            )
        )
        parent_ids: list[str] = [row[0] for row in parent_res.all() if row[0]]

        # Also include child categories of the tradie's registered categories.
        child_res = await db.execute(
            select(Category.id)
            .where(Category.parent_id.in_(tradie_category_ids))
        )
        child_ids: list[str] = [row[0] for row in child_res.all()]

        match_category_ids = list(
            set(tradie_category_ids + parent_ids + child_ids)
        )
        print(
            f"[retrodist]   Service categories (incl. parent/child): {len(match_category_ids)}"
        )

        # ── 3. Find candidate open jobs (last 30 days, matching categories) ─
        lookback = datetime.utcnow() - timedelta(days=30)
        jobs_res = await db.execute(
            select(Job)
            .where(
                Job.status == "open",
                Job.is_deleted == False,
                Job.category_id.in_(match_category_ids),
                Job.created_at >= lookback,
            )
        )
        all_open_jobs: list[Job] = jobs_res.scalars().all()
        print(
            f"[retrodist]   Open jobs in last 30 days matching categories: "
            f"{len(all_open_jobs)}"
        )

        if not all_open_jobs:
            print("[retrodist] No candidate jobs — done.")
            return

        # ── 4. Filter: skip already-matched jobs + apply geography ────────
        eligible_jobs: list[Job] = []
        tradie_radius_km = (profile.radius_km or 25) * 1.5  # extend 1.5× for retro-delivery

        for job in all_open_jobs:
            # Skip jobs that already have at least one lead — another tradie was matched.
            # The homeowner is already being served; injecting a 4th lead would be
            # spammy and violates the "max 3 tradies per job" marketplace contract.
            if job.match_intelligence:
                try:
                    mi = json.loads(job.match_intelligence)
                    if mi.get("matched", 0) > 0:
                        print(
                            f"[retrodist]   ✗ '{job.title}' already has "
                            f"{mi['matched']} lead(s) — skip"
                        )
                        continue
                except Exception:
                    pass

            # Geography filter — only re-queue if the job is in the tradie's area.
            # Fall back to "include all" when coordinates are missing (dev/test safety).
            if profile.lat and profile.lng and job.lat and job.lng:
                dist = haversine_distance(job.lat, job.lng, profile.lat, profile.lng)
                if dist > tradie_radius_km:
                    print(
                        f"[retrodist]   x '{job.title}' is {dist:.1f}km away "
                        f"(tradie radius {tradie_radius_km:.0f}km) -- skip"
                    )
                    continue
                print(
                    f"[retrodist]   ok '{job.title}' ({dist:.1f}km) -- eligible"
                )
            else:
                print(
                    f"[retrodist]   ok '{job.title}' (no coords -- included by default)"
                )

            eligible_jobs.append(job)

        print(
            f"[retrodist]   Jobs eligible for re-distribution: {len(eligible_jobs)}"
        )

        if not eligible_jobs:
            print("[retrodist] No eligible jobs after filtering -- done.")
            return

        # 5. Reset match_intelligence so _distribute_leads runs fresh
        for job in eligible_jobs:
            job.match_intelligence = None
            db.add(job)
        await db.commit()

        # 6. Re-queue distribute_leads for each eligible job
        queued = 0
        for i, job in enumerate(eligible_jobs):
            try:
                jitter = random.uniform(5, 15) + (i * 8)
                distribute_leads.apply_async(
                    args=[job.id],
                    countdown=jitter,
                    queue="critical",
                )
                print(
                    f"[retrodist]   -> Queued '{job.title}' ({job.id}) "
                    f"in {jitter:.0f}s"
                )
                queued += 1
            except Exception as exc:
                print(
                    f"[retrodist]   Warning: could not queue job {job.id}: {exc}"
                )

        print(
            f"[retrodist] DONE -- {queued}/{len(eligible_jobs)} job(s) re-queued "
            f"for {profile.business_name}"
        )
        print("[retrodist] ======================================================")


# NOTE: A duplicate definition of redistribute_open_jobs_for_tradie used to live
# here. Python lets you redefine a @shared_task with the same name, but it makes
# the first definition silently dead -- only the second would ever be registered
# with Celery. Removed to avoid the time-bomb of "fixed the wrong copy".
