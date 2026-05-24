"""
backend/routers/admin.py

Admin-only endpoints for the ProConnect platform.
All routes require role == "admin" on the authenticated user.

ENDPOINTS:
  GET    /admin/overview                          Platform stats snapshot
  GET    /admin/tradies                           All tradies (paginated, filterable)
  PATCH  /admin/tradies/{tradie_id}/verification  Set tradie verification_status
  GET    /admin/homeowners                        All homeowners (paginated)
  GET    /admin/verification/pending              All pending certs + insurance combined
  POST   /admin/verification/certifications/{cert_id}/approve
  POST   /admin/verification/certifications/{cert_id}/reject
  POST   /admin/verification/insurance/{policy_id}/approve
  POST   /admin/verification/insurance/{policy_id}/reject
  GET    /admin/jobs                              All jobs (paginated, filterable)
  GET    /admin/completed-jobs                    Completed/confirmed/closed jobs — full details
  GET    /admin/disputes                          All disputed jobs
  GET    /admin/reviews                           All reviews (for moderation)
  DELETE /admin/reviews/{review_id}               Remove a review
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from models.category import Category
from models.insurance_policy import InsurancePolicy, InsuranceStatus
from models.job import Job
from models.lead import Lead
from models.job_photo import JobPhoto
from models.review import Review
from models.tradie_category import TradieCategory
from models.tradie_change_request import (
    TradieChangeRequest,
    TradieChangeRequestStatus,
    TradieChangeRequestType,
)
from models.tradie_certification import TradieCertification, CertificationStatus
from models.tradie_pass import TradiePass
from models.tradie_profile import TradieProfile
from models.tradie_preference import TradiePreference
from models.user import User
from services.auth_service import get_current_user
from services.category_resolver import canonical_trade_category
from services.resend_service import send_admin_note_email, send_tradie_suspended_email

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# ── Auth guard ─────────────────────────────────────────────────────────────────

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


# ── Schemas ────────────────────────────────────────────────────────────────────

class RejectBody(BaseModel):
    reason: str = "other"
    note:   Optional[str] = None

class VerificationStatusBody(BaseModel):
    verification_status: str  # "pending" | "in_review" | "verified" | "rejected" | "suspended"
    note: Optional[str] = None


class SuspendTradieBody(BaseModel):
    reason: str
    confirmation: str


class AdminMessageBody(BaseModel):
    subject: str
    message: str


class ChangeRequestReviewBody(BaseModel):
    admin_note: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_tradie(profile: TradieProfile) -> dict:
    u = profile.user
    return {
        "id":                   profile.id,
        "business_name":        profile.business_name,
        "email":                u.email if u else None,
        "full_name":            u.full_name if u else None,
        "phone":                u.phone if u else None,
        "suburb":               profile.suburb,
        "state":                profile.state,
        "verification_status":  profile.verification_status,
        "is_available":         profile.is_available,
        "abn":                  profile.abn,
        "solo_or_team":         profile.solo_or_team,
        "team_size":            profile.team_size,
        "created_at":           profile.created_at,
    }


def _payload(req: TradieChangeRequest) -> dict:
    try:
        return json.loads(req.payload)
    except Exception:
        return {}


def _fmt_change_request(req: TradieChangeRequest) -> dict:
    return {
        "id": req.id,
        "type": "change_request",
        "request_type": req.request_type,
        "status": req.status,
        "tradie_id": req.tradie_id,
        "business_name": req.tradie.business_name if req.tradie else None,
        "tradie_email": req.tradie.user.email if req.tradie and req.tradie.user else None,
        "full_name": req.tradie.user.full_name if req.tradie and req.tradie.user else None,
        "payload": _payload(req),
        "note": req.note,
        "admin_note": req.admin_note,
        "solo_or_team": req.tradie.solo_or_team if req.tradie else "solo",
        "team_size": req.tradie.team_size if req.tradie else None,
        "created_at": req.created_at,
        "reviewed_at": req.reviewed_at,
    }


def _required_docs_for_category(category: Category) -> set[str]:
    slug = (category.slug or "").lower().strip()
    name = (category.name or "").lower().strip()
    key = slug or name.replace(" ", "-")

    if key in {"cleaning", "handyman"}:
        return {"abn"}
    if key in {"painting", "plastering", "flooring", "tiling", "landscaping", "glazing", "pest-control"}:
        return {"abn", "public_liability"}
    if key in {"carpentry", "concreting", "fencing"}:
        return {"abn", "public_liability", "white_card"}
    if key in {"roofing", "solar", "solar-installation", "demolition", "building", "bathroom-renovation"}:
        return {"abn", "public_liability", "trade_licence", "white_card", "swms"}
    if key in {"electrical", "electrician", "plumbing", "plumber", "gas-fitting", "gas-fitter", "hvac", "air-conditioning", "air-conditioner", "security", "waterproofing", "kitchen-renovation"}:
        return {"abn", "public_liability", "trade_licence", "white_card"}
    if any(p in name for p in ("electric", "plumb", "gas", "solar", "building", "demolition", "waterproof", "roof", "security", "air condition", "hvac", "refriger")):
        return {"abn", "public_liability", "trade_licence", "white_card"}
    return {"abn", "public_liability"}


async def _maybe_mark_profile_verified(profile_id: str | None, db: AsyncSession) -> None:
    if not profile_id:
        return

    profile_res = await db.execute(select(TradieProfile).where(TradieProfile.id == profile_id))
    profile = profile_res.scalar_one_or_none()
    if not profile or profile.verification_status in {"verified", "rejected", "suspended"}:
        return

    cat_res = await db.execute(
        select(Category)
        .join(TradieCategory, TradieCategory.category_id == Category.id)
        .where(TradieCategory.tradie_id == profile.id)
    )
    categories = cat_res.scalars().all()
    if not categories:
        return

    cert_res = await db.execute(
        select(TradieCertification)
        .options(selectinload(TradieCertification.category))
        .where(
            TradieCertification.tradie_profile_id == profile.id,
            TradieCertification.status == CertificationStatus.VERIFIED,
        )
    )
    verified_cert_ids = set()
    for cert in cert_res.scalars().all():
        verified_cert_ids.add(cert.category_id)
        if cert.category:
            canonical = await canonical_trade_category(db, cert.category)
            if canonical:
                verified_cert_ids.add(canonical.id)

    insurance_res = await db.execute(
        select(InsurancePolicy.id).where(
            InsurancePolicy.tradie_profile_id == profile.id,
            InsurancePolicy.insurance_type == "public_liability",
            InsurancePolicy.status == InsuranceStatus.VERIFIED,
        ).limit(1)
    )
    has_public_liability = insurance_res.scalar_one_or_none() is not None

    pass_res = await db.execute(select(TradiePass).where(TradiePass.tradie_id == profile.id))
    tradie_pass = pass_res.scalar_one_or_none()

    for category in categories:
        required = _required_docs_for_category(category)
        if "public_liability" in required and not has_public_liability:
            return
        if "trade_licence" in required and category.id not in verified_cert_ids:
            return
        if "white_card" in required and not (
            tradie_pass and (tradie_pass.white_card_verified or tradie_pass.wc_verified)
        ):
            return
        if "swms" in required and not (tradie_pass and tradie_pass.swms_uploaded):
            return

    profile.verification_status = "verified"
    profile.verification_notes = None
    db.add(profile)

def _fmt_cert(cert: TradieCertification) -> dict:
    profile = cert.tradie_profile
    return {
        "id":               cert.id,
        "type":             "licence",
        "tradie_id":        profile.id if profile else None,
        "business_name":    profile.business_name if profile else None,
        "tradie_email":     profile.user.email if profile and profile.user else None,
        "phone":            profile.user.phone if profile and profile.user else None,
        "category_name":    cert.category.name if cert.category else None,
        "licence_number":   cert.licence_number,
        "issuing_state":    cert.issuing_state,
        "issuing_body":     cert.issuing_body,
        "holder_name":      cert.holder_name,
        "issued_at":        cert.issued_at,
        "expires_at":       cert.expires_at,
        "photo_url":        cert.photo_url,
        "status":           cert.status,
        "rejection_reason": cert.rejection_reason,
        "rejection_note":   cert.rejection_note,
        "edit_request_note": cert.edit_request_note,
        "solo_or_team":     profile.solo_or_team if profile else "solo",
        "team_size":        profile.team_size if profile else None,
        "created_at":       cert.created_at,
    }

def _fmt_insurance(policy: InsurancePolicy) -> dict:
    profile = policy.tradie_profile
    return {
        "id":                     policy.id,
        "type":                   "insurance",
        "tradie_id":              profile.id if profile else None,
        "business_name":          profile.business_name if profile else None,
        "tradie_email":           profile.user.email if profile and profile.user else None,
        "phone":                  profile.user.phone if profile and profile.user else None,
        "insurance_type":         policy.insurance_type,
        "insurer_name":           policy.insurer_name,
        "policy_number":          policy.policy_number,
        "coverage_amount_cents":  policy.coverage_amount_cents,
        "holder_name":            policy.holder_name,
        "issued_at":              policy.issued_at,
        "expires_at":             policy.expires_at,
        "document_url":           policy.document_url,
        "status":                 policy.status,
        "rejection_reason":       policy.rejection_reason,
        "rejection_note":         policy.rejection_note,
        "edit_request_note":      policy.edit_request_note,
        "solo_or_team":           profile.solo_or_team if profile else "solo",
        "team_size":              profile.team_size if profile else None,
        "created_at":             policy.created_at,
    }


# ── GET /admin/overview ────────────────────────────────────────────────────────

@router.get("/overview")
async def get_overview(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Counts
    total_tradies_r    = await db.execute(select(func.count()).select_from(TradieProfile))
    total_homeowners_r = await db.execute(select(func.count()).select_from(User).where(User.role == "homeowner"))
    total_jobs_r       = await db.execute(select(func.count()).select_from(Job))
    open_disputes_r    = await db.execute(select(func.count()).select_from(Job).where(Job.status == "disputed"))
    completed_jobs_r   = await db.execute(select(func.count()).select_from(Job).where(Job.status.in_(["completed", "confirmed", "closed"])))

    pending_certs_r    = await db.execute(
        select(func.count()).select_from(TradieCertification)
        .where(TradieCertification.status.in_([CertificationStatus.PENDING, CertificationStatus.IN_REVIEW]))
    )
    pending_ins_r = await db.execute(
        select(func.count()).select_from(InsurancePolicy)
        .where(InsurancePolicy.status.in_([InsuranceStatus.PENDING, InsuranceStatus.IN_REVIEW]))
    )
    pending_profiles_r = await db.execute(
        select(func.count())
        .select_from(TradieProfile)
        .where(TradieProfile.verification_status.in_(["pending", "pending_review", "in_review"]))
    )
    pending_changes_r = await db.execute(
        select(func.count())
        .select_from(TradieChangeRequest)
        .where(TradieChangeRequest.status == TradieChangeRequestStatus.PENDING)
    )

    # Recent tradies (last 5)
    recent_tradies_r = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.user))
        .order_by(TradieProfile.created_at.desc())
        .limit(5)
    )
    recent_tradies = [_fmt_tradie(p) for p in recent_tradies_r.scalars().all()]

    # Recent disputes
    disputes_r = await db.execute(
        select(Job)
        .where(Job.status == "disputed")
        .order_by(Job.updated_at.desc())
        .limit(5)
    )
    disputes = [
        {
            "id": j.id, "title": j.title, "status": j.status,
            "suburb": j.suburb, "state": j.state, "updated_at": j.updated_at,
        }
        for j in disputes_r.scalars().all()
    ]

    # Recent jobs
    recent_jobs_r = await db.execute(
        select(Job)
        .order_by(Job.created_at.desc())
        .limit(5)
    )
    recent_jobs = [
        {
            "id": j.id, "title": j.title, "status": j.status,
            "suburb": j.suburb, "state": j.state, "created_at": j.created_at,
        }
        for j in recent_jobs_r.scalars().all()
    ]

    return {
        "stats": {
            "total_tradies":        total_tradies_r.scalar() or 0,
            "total_homeowners":     total_homeowners_r.scalar() or 0,
            "total_jobs":           total_jobs_r.scalar() or 0,
            "completed_jobs":       completed_jobs_r.scalar() or 0,
            "open_disputes":        open_disputes_r.scalar() or 0,
            "pending_verifications": (
                (pending_certs_r.scalar() or 0)
                + (pending_ins_r.scalar() or 0)
                + (pending_profiles_r.scalar() or 0)
                + (pending_changes_r.scalar() or 0)
            ),
        },
        "recent_tradies": recent_tradies,
        "recent_disputes": disputes,
        "recent_jobs": recent_jobs,
    }


# ── GET /admin/tradies ─────────────────────────────────────────────────────────

@router.get("/tradies")
async def list_tradies(
    page:                  int           = Query(1, ge=1),
    limit:                 int           = Query(20, ge=1, le=100),
    verification_status:   Optional[str] = Query(None),
    search:                Optional[str] = Query(None),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(TradieProfile).options(selectinload(TradieProfile.user))
    if verification_status:
        q = q.where(TradieProfile.verification_status == verification_status)
    if search:
        q = q.join(User, User.id == TradieProfile.user_id).where(
            or_(
                TradieProfile.business_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )
    count_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total   = count_r.scalar() or 0
    q       = q.order_by(TradieProfile.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result  = await db.execute(q)
    items   = [_fmt_tradie(p) for p in result.scalars().unique().all()]
    return {"total": total, "page": page, "limit": limit, "items": items}


# ── Background helper — mirrors _distribute_leads_background in jobs.py ───────

async def _redistribute_jobs_background(tradie_profile_id: str) -> None:
    """
    Runs _async_redistribute_open_jobs_for_tradie in-process without Celery.
    Used as the always-on fallback alongside the Celery task, matching the
    same two-layer pattern used by create_job → distribute_leads.
    """
    try:
        from tasks.lead_tasks import (
            _async_redistribute_open_jobs_for_tradie,
            _make_session_factory,
        )
        engine, session_factory = _make_session_factory()
        try:
            await _async_redistribute_open_jobs_for_tradie(tradie_profile_id, session_factory)
            print(f"[retrodist] Background fallback completed for tradie {tradie_profile_id}")
        finally:
            try:
                await engine.dispose()
            except Exception:
                pass
    except Exception as exc:
        print(f"[retrodist] Background fallback failed for tradie {tradie_profile_id}: {exc}")


# ── PATCH /admin/tradies/{tradie_id}/verification ──────────────────────────────

@router.patch("/tradies/{tradie_id}/verification")
async def set_tradie_verification(
    tradie_id: str,
    body: VerificationStatusBody,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.user))
        .where(TradieProfile.id == tradie_id)
    )
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found.")
    profile.verification_status = body.verification_status
    profile.verification_notes = body.note
    profile.reviewed_by = admin.id
    profile.reviewed_at = datetime.utcnow()
    if body.verification_status == "verified":
        profile.verified_at = profile.verified_at or datetime.utcnow()
        profile.is_available = True
        if profile.user:
            profile.user.is_active = True
    elif body.verification_status in {"rejected", "suspended"}:
        profile.is_available = False
    await db.commit()

    # ── Retroactive lead distribution — "late subscriber" fix ─────────────
    # Two-layer strategy (same pattern as create_job → distribute_leads):
    #   Layer 1: Celery task on critical queue (fast, distributed)
    #   Layer 2: background_tasks fallback (always runs, no Celery needed)
    # This guarantees the newly-verified tradie receives waiting jobs even
    # when Celery is down or tasks are still draining from the queue.
    if body.verification_status == "verified":
        try:
            from tasks.lead_tasks import redistribute_open_jobs_for_tradie
            redistribute_open_jobs_for_tradie.apply_async(
                args=[tradie_id],
                countdown=5,   # 5s delay lets the DB commit propagate to replicas
                queue="critical",
            )
        except Exception as _exc:
            print(
                f"[admin] Celery unavailable for retroactive distribution "
                f"(tradie {tradie_id}): {_exc} — background fallback will handle it"
            )
        # Always also schedule in-process fallback — zero dependency on Celery
        background_tasks.add_task(_redistribute_jobs_background, tradie_id)

    return {"id": tradie_id, "verification_status": profile.verification_status}


# ── POST /admin/tradies/{tradie_id}/redistribute-leads ────────────────────────

@router.post("/tradies/{tradie_id}/redistribute-leads")
async def trigger_redistribute_leads(
    tradie_id: str,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
):
    """
    Manually trigger retroactive lead distribution for a tradie.

    Use this when:
      - Tradie was verified before the redistribution trigger was deployed
      - Celery was down at the time of verification
      - Admin wants to force-retry lead matching for a specific tradie

    Runs both Celery (if available) AND an in-process background task so
    it works reliably even without a running Celery worker.
    Returns immediately; distribution happens in the background.
    """
    # Layer 1: Celery (fast, distributed)
    try:
        from tasks.lead_tasks import redistribute_open_jobs_for_tradie
        redistribute_open_jobs_for_tradie.apply_async(
            args=[tradie_id],
            countdown=2,
            queue="critical",
        )
    except Exception as _exc:
        print(
            f"[admin] Celery unavailable for manual redistribute "
            f"(tradie {tradie_id}): {_exc}"
        )

    # Layer 2: In-process fallback — always runs regardless of Celery
    background_tasks.add_task(_redistribute_jobs_background, tradie_id)

    return {
        "status": "queued",
        "message": "Lead redistribution triggered. Matching jobs will be distributed shortly.",
    }


@router.post("/categories/seed-cleaning")
async def seed_cleaning_subcategories(
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    """
    Idempotent: inserts missing cleaning subcategories (Pool Cleaning, etc.)
    into the live database. Safe to call multiple times — skips existing slugs.
    """
    import uuid as _uuid
    from models.category import Category, CategoryLevel

    NEW_SUBCATS = [
        ("cleaning-pool",       "Pool Cleaning",      "Swimming pool cleaning, chemical balancing and maintenance"),
        ("cleaning-oven",       "Oven & BBQ Cleaning","Professional oven, range hood and BBQ degreasing"),
        ("cleaning-commercial", "Commercial Cleaning","Office, retail and commercial premises cleaning"),
    ]

    parent_res = await db.execute(select(Category).where(Category.slug == "cleaning"))
    parent = parent_res.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="'cleaning' parent category not found. Run the full seed first.")

    added, skipped = [], []
    for slug, name, desc in NEW_SUBCATS:
        existing = await db.execute(select(Category).where(Category.slug == slug))
        if existing.scalar_one_or_none():
            skipped.append(name)
            continue
        db.add(Category(
            id=str(_uuid.uuid4()),
            name=name, slug=slug,
            parent_id=parent.id,
            level=CategoryLevel.SUBCATEGORY,
            is_active=True, icon_slug=None, description=desc,
        ))
        added.append(name)

    await db.commit()
    return {"added": added, "skipped": skipped}


@router.post("/tradies/{tradie_id}/suspend")
async def suspend_tradie(
    tradie_id: str,
    body: SuspendTradieBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    expected = "SUSPEND TRADIE"
    if body.confirmation.strip() != expected:
        raise HTTPException(
            status_code=422,
            detail=f"Type '{expected}' to confirm suspension.",
        )
    if len(body.reason.strip()) < 20:
        raise HTTPException(status_code=422, detail="Suspension reason must be at least 20 characters.")

    res = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.user))
        .where(TradieProfile.id == tradie_id)
    )
    profile = res.scalar_one_or_none()
    if not profile or not profile.user:
        raise HTTPException(status_code=404, detail="Tradie profile not found.")

    profile.verification_status = "suspended"
    profile.verification_notes = body.reason.strip()
    profile.is_available = False
    profile.reviewed_by = admin.id
    profile.reviewed_at = datetime.utcnow()
    profile.user.is_active = False
    db.add(profile)
    db.add(profile.user)
    await db.commit()

    try:
        await send_tradie_suspended_email(
            profile.user.email,
            profile.user.full_name or "",
            profile.business_name or profile.user.email,
            body.reason.strip(),
        )
    except Exception:
        pass

    return {
        "id": tradie_id,
        "verification_status": "suspended",
        "is_active": False,
        "message": "Tradie suspended, login disabled, and leads paused.",
    }


@router.post("/reviews/{review_id}/message")
async def message_review_author(
    review_id: str,
    body: AdminMessageBody,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Review)
        .options(selectinload(Review.homeowner))
        .where(Review.id == review_id)
    )
    review = res.scalar_one_or_none()
    if not review or not review.homeowner:
        raise HTTPException(status_code=404, detail="Review author not found.")
    await send_admin_note_email(
        review.homeowner.email,
        body.subject,
        body.message,
        full_name=review.homeowner.full_name or "",
        accent_color="#2E7D5A",
    )
    return {"sent": True}


async def _apply_change_request(req: TradieChangeRequest, db: AsyncSession) -> None:
    payload = _payload(req)
    if req.request_type == TradieChangeRequestType.SERVICE_AREAS:
        pref_res = await db.execute(
            select(TradiePreference).where(TradiePreference.tradie_id == req.tradie_id)
        )
        pref = pref_res.scalar_one_or_none()
        if not pref:
            pref = TradiePreference(id=str(uuid.uuid4()), tradie_id=req.tradie_id)
        pref.service_suburbs = json.dumps(payload.get("requested_service_suburbs") or [])
        db.add(pref)
    elif req.request_type == TradieChangeRequestType.SERVICE_ADD:
        category_id = payload.get("category_id")
        exists = await db.execute(
            select(TradieCategory).where(
                TradieCategory.tradie_id == req.tradie_id,
                TradieCategory.category_id == category_id,
            )
        )
        if category_id and not exists.scalar_one_or_none():
            db.add(TradieCategory(tradie_id=req.tradie_id, category_id=category_id))
    elif req.request_type == TradieChangeRequestType.SERVICE_REMOVE:
        category_id = payload.get("category_id")
        link_res = await db.execute(
            select(TradieCategory).where(
                TradieCategory.tradie_id == req.tradie_id,
                TradieCategory.category_id == category_id,
            )
        )
        link = link_res.scalar_one_or_none()
        if link:
            await db.delete(link)
    elif req.request_type == TradieChangeRequestType.PROFILE_IDENTITY:
        requested = payload.get("requested") or {}
        profile_res = await db.execute(select(TradieProfile).where(TradieProfile.id == req.tradie_id))
        profile = profile_res.scalar_one_or_none()
        if profile:
            for field in ("abn", "suburb", "state", "postcode"):
                if field in requested:
                    setattr(profile, field, requested[field])
            db.add(profile)


@router.post("/change-requests/{request_id}/approve")
async def approve_change_request(
    request_id: str,
    body: ChangeRequestReviewBody | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(TradieChangeRequest).where(TradieChangeRequest.id == request_id))
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Change request not found.")
    if req.status != TradieChangeRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Change request already reviewed.")
    await _apply_change_request(req, db)
    req.status = TradieChangeRequestStatus.APPROVED
    req.admin_note = body.admin_note if body else None
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    db.add(req)
    await db.commit()
    return {"id": req.id, "status": req.status}


@router.post("/change-requests/{request_id}/reject")
async def reject_change_request(
    request_id: str,
    body: ChangeRequestReviewBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(TradieChangeRequest).where(TradieChangeRequest.id == request_id))
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Change request not found.")
    if req.status != TradieChangeRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Change request already reviewed.")
    req.status = TradieChangeRequestStatus.REJECTED
    req.admin_note = body.admin_note
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    db.add(req)
    await db.commit()
    return {"id": req.id, "status": req.status}


# ── GET /admin/homeowners ──────────────────────────────────────────────────────

@router.get("/homeowners")
async def list_homeowners(
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).where(User.role == "homeowner")
    if search:
        q = q.where(
            or_(User.email.ilike(f"%{search}%"), User.full_name.ilike(f"%{search}%"))
        )
    count_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total   = count_r.scalar() or 0
    q       = q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result  = await db.execute(q)
    items   = [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name,
            "phone": u.phone, "is_active": u.is_active,
            "email_verified": u.email_verified, "created_at": u.created_at,
        }
        for u in result.scalars().all()
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}


# ── GET /admin/verification/pending ───────────────────────────────────────────

@router.get("/verification/pending")
async def get_pending_verifications(
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    PENDING_STATUSES = [CertificationStatus.PENDING, CertificationStatus.IN_REVIEW]

    certs_r = await db.execute(
        select(TradieCertification)
        .options(
            selectinload(TradieCertification.tradie_profile).selectinload(TradieProfile.user),
            selectinload(TradieCertification.category),
        )
        .where(TradieCertification.status.in_(PENDING_STATUSES))
        .order_by(TradieCertification.created_at.asc())
    )
    certs = [_fmt_cert(c) for c in certs_r.scalars().all()]

    ins_r = await db.execute(
        select(InsurancePolicy)
        .options(
            selectinload(InsurancePolicy.tradie_profile).selectinload(TradieProfile.user),
        )
        .where(InsurancePolicy.status.in_(PENDING_STATUSES))
        .order_by(InsurancePolicy.created_at.asc())
    )
    insurance = [_fmt_insurance(p) for p in ins_r.scalars().all()]

    # Pending tradie profile approvals
    profiles_r = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.user))
        .where(TradieProfile.verification_status.in_(["pending", "pending_review", "in_review"]))
        .order_by(TradieProfile.created_at.asc())
    )
    profiles = [
        {
            "id": p.id, "type": "profile",
            "tradie_id": p.id,
            "business_name": p.business_name,
            "tradie_email": p.user.email if p.user else None,
            "full_name": p.user.full_name if p.user else None,
            "phone": p.user.phone if p.user else None,
            "suburb": p.suburb, "state": p.state,
            "abn": p.abn,
            "solo_or_team": p.solo_or_team,
            "team_size": p.team_size,
            "created_at": p.created_at,
            "verification_status": p.verification_status,
        }
        for p in profiles_r.scalars().all()
    ]

    changes_r = await db.execute(
        select(TradieChangeRequest)
        .options(
            selectinload(TradieChangeRequest.tradie).selectinload(TradieProfile.user),
        )
        .where(TradieChangeRequest.status == TradieChangeRequestStatus.PENDING)
        .order_by(TradieChangeRequest.created_at.asc())
    )
    change_requests = [_fmt_change_request(req) for req in changes_r.scalars().all()]

    return {
        "certifications": certs,
        "insurance":      insurance,
        "profiles":       profiles,
        "change_requests": change_requests,
        "total":          len(certs) + len(insurance) + len(profiles) + len(change_requests),
    }


# ── POST /admin/verification/certifications/{cert_id}/approve ─────────────────

@router.post("/verification/certifications/{cert_id}/approve")
async def approve_certification(
    cert_id: str,
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    res  = await db.execute(select(TradieCertification).where(TradieCertification.id == cert_id))
    cert = res.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found.")
    cert.status      = CertificationStatus.VERIFIED
    cert.verified_by = admin.id
    cert.verified_at = datetime.utcnow()
    cert.rejection_reason = None
    cert.rejection_note   = None
    await _maybe_mark_profile_verified(cert.tradie_profile_id, db)
    await db.commit()
    return {"id": cert_id, "status": cert.status}


# ── POST /admin/verification/certifications/{cert_id}/reject ──────────────────

@router.post("/verification/certifications/{cert_id}/reject")
async def reject_certification(
    cert_id: str,
    body:  RejectBody,
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    res  = await db.execute(select(TradieCertification).where(TradieCertification.id == cert_id))
    cert = res.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found.")
    cert.status           = CertificationStatus.REJECTED
    cert.rejection_reason = body.reason
    cert.rejection_note   = body.note
    cert.verified_by      = admin.id
    cert.verified_at      = datetime.utcnow()
    await db.commit()
    return {"id": cert_id, "status": cert.status}


# ── POST /admin/verification/insurance/{policy_id}/approve ────────────────────

@router.post("/verification/insurance/{policy_id}/approve")
async def approve_insurance(
    policy_id: str,
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    res    = await db.execute(select(InsurancePolicy).where(InsurancePolicy.id == policy_id))
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Insurance policy not found.")
    policy.status      = InsuranceStatus.VERIFIED
    policy.verified_by = admin.id
    policy.verified_at = datetime.utcnow()
    policy.rejection_reason = None
    policy.rejection_note   = None
    await _maybe_mark_profile_verified(policy.tradie_profile_id, db)
    await db.commit()
    return {"id": policy_id, "status": policy.status}


# ── POST /admin/verification/insurance/{policy_id}/reject ─────────────────────

@router.post("/verification/insurance/{policy_id}/reject")
async def reject_insurance(
    policy_id: str,
    body:  RejectBody,
    admin: User = Depends(require_admin),
    db:    AsyncSession = Depends(get_db),
):
    res    = await db.execute(select(InsurancePolicy).where(InsurancePolicy.id == policy_id))
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Insurance policy not found.")
    policy.status           = InsuranceStatus.REJECTED
    policy.rejection_reason = body.reason
    policy.rejection_note   = body.note
    policy.verified_by      = admin.id
    policy.verified_at      = datetime.utcnow()
    await db.commit()
    return {"id": policy_id, "status": policy.status}


# ── GET /admin/jobs ────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Build base filter for count and data query
    filters = []
    if status:
        filters.append(Job.status == status)
    if search:
        filters.append(Job.title.ilike(f"%{search}%"))

    count_r = await db.execute(select(func.count(Job.id)).where(*filters))
    total   = count_r.scalar() or 0

    q = (
        select(Job)
        .options(selectinload(Job.photos))
        .where(*filters)
        .order_by(Job.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(q)
    items  = [
        {
            "id": j.id, "title": j.title, "status": j.status,
            "suburb": j.suburb, "state": j.state,
            "homeowner_id": j.homeowner_id,
            "photo_before_url": j.photo_before_url,
            "photo_after_url":  j.photo_after_url,
            "completion_note":  j.completion_note,
            "after_photos": [{"url": p.url, "id": p.id} for p in (j.photos or [])],
            "created_at": j.created_at, "updated_at": j.updated_at,
        }
        for j in result.scalars().all()
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}


# ── GET /admin/disputes ────────────────────────────────────────────────────────

async def _build_dispute_payload(j: Job, db: AsyncSession) -> dict:
    """
    Compose the full dispute context for the admin Disputes view:
      * homeowner contact + their dispute reason
      * tradie contact + their completion note + accepted quote details
      * before/after photos
      * full job description + category + location
      * recent timeline events (so admin sees the whole story without leaving the page)
    """
    from models.job_event import JobEvent
    from models.quote import Quote
    from models.lead import Lead
    from models.job_photo import JobPhoto
    from models.user import User as UserModel
    from models.tradie_profile import TradieProfile as TP
    from models.category import Category as Cat

    # Dispute reason from the JobEvent that flipped the job to 'disputed'.
    dispute_event_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == j.id, JobEvent.action == "status_change")
        .order_by(JobEvent.created_at.desc())
    )
    dispute_reason = None
    dispute_raised_at = None
    dispute_raised_by_role = None
    for ev in dispute_event_res.scalars().all():
        nv = ev.new_value or {}
        if nv.get("status") == "disputed":
            note = ev.note or ""
            # Stored as "Homeowner raised dispute: <reason>"; strip the prefix.
            for prefix in ("Homeowner raised dispute: ", "Homeowner raised dispute:"):
                if note.startswith(prefix):
                    note = note[len(prefix):].strip()
                    break
            dispute_reason = note or None
            dispute_raised_at = ev.created_at
            dispute_raised_by_role = ev.actor_role
            break

    # Recent timeline -- last 10 events.
    tl_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == j.id)
        .order_by(JobEvent.created_at.desc())
        .limit(10)
    )
    timeline = [
        {
            "action":     ev.action,
            "actor_role": ev.actor_role,
            "note":       ev.note,
            "old_value":  ev.old_value,
            "new_value":  ev.new_value,
            "created_at": ev.created_at,
        }
        for ev in tl_res.scalars().all()
    ]

    # Homeowner contact
    hw_res = await db.execute(select(UserModel).where(UserModel.id == j.homeowner_id))
    hw = hw_res.scalar_one_or_none()

    # Category
    cat_res = await db.execute(select(Cat).where(Cat.id == j.category_id))
    cat = cat_res.scalar_one_or_none()

    # Tradie via accepted quote (preferred -- this is the tradie who actually did the work).
    accepted_q_res = await db.execute(
        select(Quote, TP, UserModel)
        .join(TP,        TP.id == Quote.tradie_id)
        .join(UserModel, UserModel.id == TP.user_id)
        .join(Lead,      Lead.id == Quote.lead_id)
        .where(Lead.job_id == j.id, Quote.status == "accepted")
        .limit(1)
    )
    accepted_row = accepted_q_res.first()
    tradie_info = None
    if accepted_row:
        q_obj, tp_obj, tu_obj = accepted_row
        tradie_info = {
            "tradie_profile_id":   tp_obj.id,
            "business_name":       tp_obj.business_name,
            "full_name":           tu_obj.full_name,
            "email":               tu_obj.email,
            "phone":               tu_obj.phone,
            "verification_status": tp_obj.verification_status,
            "quote_amount":        q_obj.amount,
            "quote_message":       q_obj.message,
        }
    else:
        # Fallback to any tradie with a lead on this job (shouldn't normally happen
        # for completed-then-disputed jobs, but covers partial_stop disputes).
        lead_res = await db.execute(
            select(TP, UserModel)
            .join(UserModel, UserModel.id == TP.user_id)
            .join(Lead,      Lead.tradie_id == TP.id)
            .where(Lead.job_id == j.id)
            .limit(1)
        )
        lead_row = lead_res.first()
        if lead_row:
            tp_obj, tu_obj = lead_row
            tradie_info = {
                "tradie_profile_id":   tp_obj.id,
                "business_name":       tp_obj.business_name,
                "full_name":           tu_obj.full_name,
                "email":               tu_obj.email,
                "phone":               tu_obj.phone,
                "verification_status": tp_obj.verification_status,
                "quote_amount":        None,
                "quote_message":       None,
            }

    # After-photos (the JobPhoto rows tradies upload mid/post job).
    photo_res = await db.execute(
        select(JobPhoto).where(JobPhoto.job_id == j.id).order_by(JobPhoto.created_at.desc())
    )
    after_photos = [{"id": p.id, "url": p.url} for p in photo_res.scalars().all()]

    # Tradie responses to the dispute -- text + evidence URLs, oldest first
    # so admin reads them as a conversation.
    resp_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == j.id, JobEvent.action == "dispute_response")
        .order_by(JobEvent.created_at.asc())
    )
    tradie_responses = [
        {
            "id":          ev.id,
            "actor_id":    ev.actor_id,
            "actor_role":  ev.actor_role,
            "response":    ev.note,
            "evidence_url": (ev.new_value or {}).get("evidence_url"),
            "created_at":  ev.created_at,
        }
        for ev in resp_res.scalars().all()
    ]

    return {
        "id":          j.id,
        "title":       j.title,
        "description": j.description,
        "category":    cat.name if cat else None,
        "status":      j.status,
        "suburb":      j.suburb,
        "state":       j.state,
        "postcode":    j.postcode,
        "urgency":     j.urgency,
        "created_at":           j.created_at,
        "completed_at":         j.completed_at,
        "confirmed_by_user_at": j.confirmed_by_user_at,
        "updated_at":           j.updated_at,
        "homeowner": {
            "id":    hw.id        if hw else None,
            "name":  hw.full_name if hw else None,
            "email": hw.email     if hw else None,
            "phone": hw.phone     if hw else None,
        },
        "tradie":           tradie_info,
        "photo_before_url": j.photo_before_url,
        "photo_after_url":  j.photo_after_url,
        "completion_note":  j.completion_note,   # tradie's note when they marked complete
        "after_photos":     after_photos,
        "tradie_responses": tradie_responses,
        # ── Dispute-specific fields ─────────────────────────────────────────
        "dispute_reason":         dispute_reason,
        "dispute_raised_at":      dispute_raised_at,
        "dispute_raised_by_role": dispute_raised_by_role,
        "timeline":               timeline,
    }


@router.get("/disputes")
async def list_disputes(
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List every disputed job with the FULL context admins need to adjudicate:
    homeowner's reason, tradie's completion note, before/after photos, contacts,
    accepted quote, recent timeline. Previously this endpoint only returned a
    handful of fields and admins couldn't see the actual complaint.
    """
    result = await db.execute(
        select(Job)
        .where(Job.status == "disputed")
        .order_by(Job.updated_at.desc())
    )
    jobs = result.scalars().all()
    items = []
    for j in jobs:
        items.append(await _build_dispute_payload(j, db))
    return {"items": items, "total": len(items)}


@router.get("/disputes/{job_id}")
async def get_dispute(
    job_id: str,
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Detail view for a single disputed job. Same shape as the list payload."""
    res = await db.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "disputed":
        raise HTTPException(status_code=400, detail=f"Job is not disputed (status={job.status})")
    return await _build_dispute_payload(job, db)


# ── GET /admin/reviews ─────────────────────────────────────────────────────────

@router.get("/reviews")
async def list_reviews(
    page:  int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q       = select(Review).order_by(Review.created_at.desc())
    count_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total   = count_r.scalar() or 0
    q       = q.offset((page - 1) * limit).limit(limit)
    result  = await db.execute(q)
    items   = [
        {
            "id": r.id, "job_id": r.job_id, "tradie_id": r.tradie_id,
            "homeowner_id": r.homeowner_id, "rating": r.rating,
            "comment": r.comment, "created_at": r.created_at,
        }
        for r in result.scalars().all()
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}



@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: str,
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res    = await db.execute(select(Review).where(Review.id == review_id))
    review = res.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    await db.delete(review)
    await db.commit()


# ── GET /admin/completed-jobs ──────────────────────────────────────────────────

@router.get("/completed-jobs")
async def list_completed_jobs(
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from models.quote import Quote

    DONE_STATUSES = ["completed", "confirmed", "closed"]
    filter_statuses = [status] if status and status in DONE_STATUSES else DONE_STATUSES

    filters = [Job.status.in_(filter_statuses)]
    if search:
        filters.append(Job.title.ilike(f"%{search}%"))

    count_r = await db.execute(select(func.count(Job.id)).where(*filters))
    total   = count_r.scalar() or 0

    jobs_res = await db.execute(
        select(Job)
        .options(
            selectinload(Job.homeowner),
            selectinload(Job.photos),
            selectinload(Job.review),
            selectinload(Job.category),
        )
        .where(*filters)
        .order_by(Job.completed_at.desc().nulls_last(), Job.updated_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    jobs = jobs_res.scalars().all()

    if not jobs:
        return {"total": total, "page": page, "limit": limit, "items": []}

    # Bulk-fetch accepted quotes + tradie info for these jobs
    job_ids = [j.id for j in jobs]
    quotes_res = await db.execute(
        select(Quote, TradieProfile, User)
        .join(Lead,          Lead.id           == Quote.lead_id)
        .join(TradieProfile, TradieProfile.id  == Quote.tradie_id)
        .join(User,          User.id           == TradieProfile.user_id)
        .where(Lead.job_id.in_(job_ids), Quote.status == "accepted")
    )

    # Map job_id -> (quote, tradie_profile, tradie_user)
    quote_map: dict = {}
    for row in quotes_res.all():
        quote, tradie_profile, tradie_user = row
        lead_res = await db.execute(select(Lead).where(Lead.id == quote.lead_id))
        lead = lead_res.scalar_one_or_none()
        if lead and lead.job_id not in quote_map:
            quote_map[lead.job_id] = (quote, tradie_profile, tradie_user)

    items = []
    for j in jobs:
        hw  = j.homeowner
        cat = j.category
        rev = j.review
        q_data = quote_map.get(j.id)
        tradie_info = None
        if q_data:
            _q, _tp, _tu = q_data
            tradie_info = {
                "tradie_profile_id":   _tp.id,
                "business_name":       _tp.business_name,
                "full_name":           _tu.full_name,
                "email":               _tu.email,
                "phone":               _tu.phone,
                "verification_status": _tp.verification_status,
                "quote_amount":        _q.amount,
                "quote_message":       _q.message,
            }

        items.append({
            "id":          j.id,
            "title":       j.title,
            "description": j.description,
            "category":    cat.name if cat else None,
            "status":      j.status,
            "suburb":      j.suburb,
            "state":       j.state,
            "postcode":    j.postcode,
            "urgency":     j.urgency,
            "created_at":           j.created_at,
            "completed_at":         j.completed_at,
            "confirmed_by_user_at": j.confirmed_by_user_at,
            "updated_at":           j.updated_at,
            "homeowner": {
                "id":    hw.id        if hw else None,
                "name":  hw.full_name if hw else None,
                "email": hw.email     if hw else None,
                "phone": hw.phone     if hw else None,
            },
            "tradie": tradie_info,
            "photo_before_url": j.photo_before_url,
            "completion_note":  j.completion_note,
            "after_photos": [{"id": p.id, "url": p.url} for p in (j.photos or [])],
            "review": {
                "id":         rev.id,
                "rating":     rev.rating,
                "comment":    rev.comment,
                "status":     rev.status,
                "created_at": rev.created_at,
            } if rev else None,
        })

    return {"total": total, "page": page, "limit": limit, "items": items}


# ═══════════════════════════════════════════════════════════════════════════
# UNCATEGORISED SERVICE-REQUEST TRIAGE
#
# When a homeowner submits a request that doesn't match any of the 24 trades
# (either via POST /jobs/uncategorised, or because POST /jobs couldn't
# resolve the slug), the job lands in the sentinel 'other-services' category
# with status='open' and a JobEvent action='uncategorised_request'. Admin
# uses these endpoints to either route it into a real trade or close it out
# with a polite "not supported" email.
# ═══════════════════════════════════════════════════════════════════════════

from services.uncategorised_service import SENTINEL_OTHER_SLUG, get_sentinel_category


class ClassifyUncategorisedRequest(BaseModel):
    category_slug: str
    note:          Optional[str] = None


class CloseUncategorisedRequest(BaseModel):
    admin_note: Optional[str] = None


@router.get("/uncategorised")
async def list_uncategorised_requests(
    page:  int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List jobs currently sitting in the sentinel 'other-services' category and
    still awaiting triage (status == 'open'). These need admin to either
    classify them into a real trade or close them out.
    """
    sentinel = await get_sentinel_category(db)

    filters = [Job.category_id == sentinel.id, Job.status == "open", Job.is_deleted == False]
    count_r = await db.execute(select(func.count(Job.id)).where(*filters))
    total = count_r.scalar() or 0

    q = (
        select(Job)
        .where(*filters)
        .order_by(Job.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(q)
    items = [
        {
            "id":            j.id,
            "title":         j.title,
            "description":   j.description,
            "homeowner_id":  j.homeowner_id,
            "suburb":        j.suburb,
            "state":         j.state,
            "postcode":      j.postcode,
            "contact_name":  j.contact_name,
            "contact_phone": j.contact_phone,
            "contact_email": j.contact_email,
            "created_at":    j.created_at,
        }
        for j in res.scalars().all()
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}


@router.post("/uncategorised/{job_id}/classify")
async def classify_uncategorised_request(
    job_id: str,
    body:   ClassifyUncategorisedRequest,
    background_tasks: BackgroundTasks,
    admin:  User = Depends(require_admin),
    db:     AsyncSession = Depends(get_db),
):
    """
    Admin assigns a real category to an uncategorised request. The job's
    category_id is updated to the resolved trade and lead distribution is
    re-triggered immediately so it joins the normal matching flow.
    """
    job_res = await db.execute(select(Job).where(Job.id == job_id, Job.is_deleted == False))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sentinel = await get_sentinel_category(db)
    if job.category_id != sentinel.id:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not in the uncategorised bucket (current category != '{SENTINEL_OTHER_SLUG}').",
        )

    target = await resolve_trade_category(db, body.category_slug)
    if not target:
        raise HTTPException(status_code=400, detail=f"Unknown target category '{body.category_slug}'.")

    old_cat_id = job.category_id
    job.category_id = target.id
    # Also reset match_intelligence so the distribute_leads idempotency guard
    # doesn't refuse the retry.
    job.match_intelligence = None
    job.updated_at = datetime.utcnow()
    db.add(job)

    # Audit trail
    from models.job_event import JobEvent
    db.add(JobEvent(
        job_id=job.id,
        actor_id=admin.id,
        actor_role="admin",
        action="uncategorised_classified",
        old_value={"category_id": old_cat_id},
        new_value={"category_id": target.id, "category_slug": target.slug},
        note=(body.note or f"Admin classified uncategorised request into '{target.name}'."),
    ))
    await db.commit()

    # Trigger lead distribution (Celery preferred, in-process fallback).
    celery_queued = False
    try:
        from tasks.lead_tasks import distribute_leads
        import asyncio
        task = await asyncio.get_event_loop().run_in_executor(
            None, lambda: distribute_leads.apply_async(args=[job.id], queue="critical"),
        )
        job.lead_task_id = task.id
        db.add(job)
        await db.commit()
        celery_queued = True
    except Exception:
        pass

    if not celery_queued:
        from routers.jobs import _distribute_leads_background
        background_tasks.add_task(_distribute_leads_background, job.id)

    return {
        "message": f"Job classified into '{target.name}' and lead distribution queued.",
        "job_id":  job.id,
        "category_id": target.id,
        "category_slug": target.slug,
    }


@router.post("/uncategorised/{job_id}/close")
async def close_uncategorised_request(
    job_id: str,
    body:   CloseUncategorisedRequest,
    admin:  User = Depends(require_admin),
    db:     AsyncSession = Depends(get_db),
):
    """
    Admin closes an uncategorised request as not supported. Sets status to
    'cancelled' (terminal), writes an audit event with the admin's note, and
    sends the homeowner a polite "we can't help with this one" email.
    """
    job_res = await db.execute(select(Job).where(Job.id == job_id, Job.is_deleted == False))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sentinel = await get_sentinel_category(db)
    if job.category_id != sentinel.id:
        raise HTTPException(
            status_code=400,
            detail="Job is not in the uncategorised bucket.",
        )
    if job.status not in ("open", "quoted"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot close a job in '{job.status}' status.",
        )

    # Use the state machine to keep the audit trail consistent. open -> cancelled
    # is already allowed for admin.
    try:
        from services.job_state_machine import JobStateMachine, InvalidTransitionError
        await JobStateMachine.admin_transition(
            job=job,
            new_status="cancelled",
            admin_user_id=admin.id,
            db=db,
            note=(
                (body.admin_note or "")
                + (" -- " if body.admin_note else "")
                + "Closed by admin from uncategorised triage."
            ),
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Additional explicit triage audit row so the admin tab can filter on it.
    from models.job_event import JobEvent
    db.add(JobEvent(
        job_id=job.id,
        actor_id=admin.id,
        actor_role="admin",
        action="uncategorised_closed",
        old_value={"status": "open"},
        new_value={"status": "cancelled"},
        note=body.admin_note or "Closed as not supported.",
    ))
    await db.commit()

    # Polite email to the homeowner. Best-effort.
    try:
        homeowner_res = await db.execute(select(User).where(User.id == job.homeowner_id))
        homeowner = homeowner_res.scalar_one_or_none()
        if homeowner:
            from services.resend_service import send_uncategorised_not_supported_email
            await send_uncategorised_not_supported_email(
                to_email=homeowner.email,
                full_name=homeowner.full_name or "",
                description_excerpt=job.description or job.title,
                admin_note=body.admin_note,
            )
    except Exception:
        pass

    return {"message": "Uncategorised request closed.", "job_id": job.id}


# ═══════════════════════════════════════════════════════════════════════════
# DISPUTE RESOLUTION
#
# Four resolution paths. Each picks the right end-state, notifies both parties
# via tailored emails, and writes a clear audit row so the timeline reflects
# the decision -- not just a generic "closed".
#
#   refund_homeowner -> closed       (full refund issued)
#   partial_refund   -> closed       (partial refund issued; remainder paid out)
#   side_tradie      -> confirmed    (work accepted)
#   redo_work        -> in_progress  (tradie returns; lifecycle re-enters active)
# ═══════════════════════════════════════════════════════════════════════════

RESOLUTION_TO_STATUS = {
    "refund_homeowner": "closed",
    "partial_refund":   "closed",
    "side_tradie":      "confirmed",
    "redo_work":        "in_progress",
}


class ResolveDisputeRequest(BaseModel):
    resolution: str   # one of RESOLUTION_TO_STATUS keys
    note:       Optional[str] = None
    refund_amount: Optional[float] = None  # only meaningful for partial_refund


@router.post("/disputes/{job_id}/resolve")
async def resolve_dispute(
    job_id: str,
    body:   ResolveDisputeRequest,
    admin:  User = Depends(require_admin),
    db:     AsyncSession = Depends(get_db),
):
    """
    Admin resolves a dispute. Picks the new status from RESOLUTION_TO_STATUS,
    writes the audit row, transitions the job, and emails both parties with
    the decision. The frontend Disputes tab refreshes via the existing
    job:status_changed WebSocket broadcast.
    """
    from models.job_event import JobEvent
    from services.job_state_machine import JobStateMachine, InvalidTransitionError

    if body.resolution not in RESOLUTION_TO_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown resolution '{body.resolution}'. Valid: {list(RESOLUTION_TO_STATUS)}",
        )
    if body.resolution == "partial_refund" and (body.refund_amount is None or body.refund_amount <= 0):
        raise HTTPException(status_code=400, detail="partial_refund requires a positive refund_amount.")

    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "disputed":
        raise HTTPException(status_code=400, detail=f"Job is not disputed (status={job.status}).")

    target_status = RESOLUTION_TO_STATUS[body.resolution]
    audit_note = (body.note or "").strip() or f"Resolution: {body.resolution}"
    if body.resolution == "partial_refund":
        audit_note = f"{audit_note} (refund: ${body.refund_amount:.2f})"

    # Transition via state machine -- this also broadcasts job:status_changed.
    try:
        await JobStateMachine.admin_transition(
            job=job,
            new_status=target_status,
            admin_user_id=admin.id,
            db=db,
            note=audit_note,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Detailed audit row carrying the structured resolution payload so the
    # admin Disputes view + post-mortem analytics can read the decision later.
    db.add(JobEvent(
        job_id=job.id,
        actor_id=admin.id,
        actor_role="admin",
        action="dispute_resolved",
        old_value={"status": "disputed"},
        new_value={
            "status":        target_status,
            "resolution":    body.resolution,
            "refund_amount": body.refund_amount,
        },
        note=body.note or None,
    ))
    await db.commit()

    # ── Notify both parties. Best-effort -- never raise. ────────────────────
    try:
        from models.user import User as UserModel
        from models.quote import Quote
        from models.lead import Lead
        from models.tradie_profile import TradieProfile as TP
        from services.resend_service import (
            send_dispute_resolved_to_homeowner_email,
            send_dispute_resolved_to_tradie_email,
        )

        hw_res = await db.execute(select(UserModel).where(UserModel.id == job.homeowner_id))
        homeowner = hw_res.scalar_one_or_none()
        if homeowner and homeowner.email:
            await send_dispute_resolved_to_homeowner_email(
                to_email=homeowner.email,
                full_name=homeowner.full_name or "",
                job_title=job.title,
                resolution=body.resolution,
                admin_note=body.note,
                refund_amount=body.refund_amount,
            )

        # Tradie via accepted quote, fallback to any lead.
        accepted_res = await db.execute(
            select(Quote, TP, UserModel)
            .join(TP,        TP.id == Quote.tradie_id)
            .join(UserModel, UserModel.id == TP.user_id)
            .join(Lead,      Lead.id == Quote.lead_id)
            .where(Lead.job_id == job.id, Quote.status == "accepted").limit(1)
        )
        accepted = accepted_res.first()
        tradie_user = tradie_profile = None
        if accepted:
            _q, tradie_profile, tradie_user = accepted
        else:
            lead_res = await db.execute(
                select(TP, UserModel)
                .join(UserModel, UserModel.id == TP.user_id)
                .join(Lead,      Lead.tradie_id == TP.id)
                .where(Lead.job_id == job.id).limit(1)
            )
            lead_row = lead_res.first()
            if lead_row:
                tradie_profile, tradie_user = lead_row

        if tradie_user and tradie_user.email:
            await send_dispute_resolved_to_tradie_email(
                to_email=tradie_user.email,
                full_name=tradie_user.full_name or "",
                business_name=(tradie_profile.business_name if tradie_profile else ""),
                job_title=job.title,
                resolution=body.resolution,
                admin_note=body.note,
                refund_amount=body.refund_amount,
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Resolution notification failed for job %s: %s", job.id, exc,
        )

    return {
        "message":     f"Dispute resolved -- {body.resolution}.",
        "job_id":      job.id,
        "new_status":  target_status,
        "resolution":  body.resolution,
    }
