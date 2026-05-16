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
  GET    /admin/disputes                          All disputed jobs
  GET    /admin/reviews                           All reviews (for moderation)
  DELETE /admin/reviews/{review_id}               Remove a review
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from models.category import Category
from models.insurance_policy import InsurancePolicy, InsuranceStatus
from models.job import Job
from models.lead import Lead
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


# ── PATCH /admin/tradies/{tradie_id}/verification ──────────────────────────────

@router.patch("/tradies/{tradie_id}/verification")
async def set_tradie_verification(
    tradie_id: str,
    body: VerificationStatusBody,
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
    return {"id": tradie_id, "verification_status": profile.verification_status}


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
            "business_name": p.business_name,
            "tradie_email": p.user.email if p.user else None,
            "full_name": p.user.full_name if p.user else None,
            "suburb": p.suburb, "state": p.state,
            "abn": p.abn, "created_at": p.created_at,
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
    q = select(Job)
    if status:
        q = q.where(Job.status == status)
    if search:
        q = q.where(Job.title.ilike(f"%{search}%"))
    count_r = await db.execute(select(func.count()).select_from(q.subquery()))
    total   = count_r.scalar() or 0
    q       = q.order_by(Job.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result  = await db.execute(q)
    items   = [
        {
            "id": j.id, "title": j.title, "status": j.status,
            "suburb": j.suburb, "state": j.state,
            "homeowner_id": j.homeowner_id,
            "created_at": j.created_at, "updated_at": j.updated_at,
        }
        for j in result.scalars().all()
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}


# ── GET /admin/disputes ────────────────────────────────────────────────────────

@router.get("/disputes")
async def list_disputes(
    _:  User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .where(Job.status == "disputed")
        .order_by(Job.updated_at.desc())
    )
    items = [
        {
            "id": j.id, "title": j.title, "status": j.status,
            "suburb": j.suburb, "state": j.state,
            "homeowner_id": j.homeowner_id,
            "completion_note": j.completion_note,
            "created_at": j.created_at, "updated_at": j.updated_at,
        }
        for j in result.scalars().all()
    ]
    return {"items": items, "total": len(items)}


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


# ── DELETE /admin/reviews/{review_id} ─────────────────────────────────────────

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
