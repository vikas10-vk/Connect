"""
backend/routers/tradies.py

UPDATED — adds the full tradie verification infrastructure on top of the
existing endpoints. Every existing endpoint is preserved exactly.

NEW ENDPOINTS:
  POST   /onboarding/submit              (updated — now creates owner TeamMember row + sets is_primary)
  GET    /onboarding/status              Verification status dashboard (profile + certs + insurance + workers)
  GET    /categories/tree                3-level category tree for the booking wizard + onboarding
  POST   /certifications/submit          Submit a licence number for a category
  GET    /certifications/me              List all certifications for the current tradie
  DELETE /certifications/{cert_id}       Delete a pending cert (cannot delete verified)
  POST   /insurance/submit               Submit an insurance policy
  GET    /insurance/me                   List all insurance policies for the current tradie
  DELETE /insurance/{policy_id}          Delete a pending insurance policy
  PATCH  /availability/toggle            Pause / resume bookings + Redis cache invalidation
  POST   /team/workers                   Business owner adds a worker
  GET    /team/workers                   List all workers in the current business
  PATCH  /team/workers/{member_id}       Update a worker (owner only)
  DELETE /team/workers/{member_id}       Deactivate a worker (owner only)
"""

import json
import os
import uuid
import math
from datetime import date, datetime
from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
import bcrypt as _bcrypt
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from models.category import Category, CategoryLevel
from models.insurance_policy import InsurancePolicy, InsuranceStatus, InsuranceType
from models.inquiry import Inquiry
from models.job import Job
from models.lead import Lead
from models.review import Review
from models.service_question import ServiceQuestion
from models.team_member import TeamMember, TeamMemberRole
from models.tradie_category import TradieCategory
from models.tradie_certification import (
    TradieCertification,
    CertificationStatus,
    IssuingState,
)
from models.tradie_profile import TradieProfile
from models.tradie_preference import TradiePreference
from models.user import User
from schemas.lead_schema import LeadResponse
from schemas.tradie_schema import (
    CategoryBrief,
    InquiryCreate,
    InquiryResponse,
    ReviewResponse,
    TradieListItem,
    TradieListResponse,
    TradieProfileCreate,
    TradieProfileResponse,
    TradieProfileUpdate,
    TradiePublicResponse,
)
from services.auth_service import get_current_user
from services.geocoding_service import geocode_tradie_suburb
from services.notification_service import notify_tradie_new_inquiry
from services.category_resolver import resolve_to_canonical_trade

# ── Constants ──────────────────────────────────────────────────────────────
URGENT_VALUES        = {"asap", "emergency"}
HIGH_VALUE_THRESHOLD = 1000.0

# The single canonical "approved" status value used everywhere.
# Django admin sets verification_status = "verified" — this constant
# ensures every gate in this file matches that value consistently.
APPROVED_STATUS = "verified"


router = APIRouter(prefix="/api/v1/tradies", tags=["Tradies"])


# ── Redis dependency ───────────────────────────────────────────────────────
async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        db=1,
        decode_responses=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS — existing
# ═══════════════════════════════════════════════════════════════════════════

class OnboardingSubmitRequest(BaseModel):
    business_name : str                     = Field(..., min_length=2, max_length=255)
    abn           : str                     = Field(..., min_length=11, max_length=20)
    suburb        : str                     = Field(..., min_length=1, max_length=100)
    state         : str                     = Field(..., min_length=2, max_length=10)
    postcode      : str                     = Field(..., min_length=4, max_length=10)
    solo_or_team  : Literal["solo", "team"] = "solo"
    team_size     : str | None              = None
    phone         : str | None              = None
    bio           : str | None              = None
    category_ids  : list[str]               = Field(default_factory=list, min_length=1)
    radius_km     : int                     = Field(default=25, ge=5, le=50)


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS — new
# ═══════════════════════════════════════════════════════════════════════════

class CertificationSubmitRequest(BaseModel):
    category_id    : str             = Field(..., description="Level-1 category ID this licence covers")
    licence_number : str             = Field(..., min_length=2, max_length=100)
    issuing_state  : str             = Field(..., description="VIC | NSW | QLD | WA | SA | TAS | NT | ACT")
    issuing_body   : Optional[str]   = Field(None, max_length=100)
    holder_name    : str             = Field(..., min_length=2, max_length=255)
    issued_at      : Optional[date]  = None
    expires_at     : Optional[date]  = None
    photo_url      : Optional[str]   = Field(None)
    team_member_id : Optional[str]   = Field(None)


class InsurancePolicySubmitRequest(BaseModel):
    insurance_type        : str            = Field(default=InsuranceType.PUBLIC_LIABILITY)
    insurer_name          : str            = Field(..., min_length=2, max_length=255)
    policy_number         : str            = Field(..., min_length=2, max_length=100)
    coverage_amount_cents : int            = Field(..., gt=0)
    holder_name           : str            = Field(..., min_length=2, max_length=255)
    issued_at             : Optional[date] = None
    expires_at            : date           = Field(...)
    document_url          : Optional[str]  = Field(None)


class WorkerInviteRequest(BaseModel):
    full_name  : str = Field(..., min_length=2, max_length=255)
    email      : str = Field(..., min_length=5, max_length=255)
    phone_real : str = Field(..., min_length=8, max_length=20)
    password   : str = Field(..., min_length=8)


class WorkerUpdateRequest(BaseModel):
    full_name  : Optional[str]  = Field(None, max_length=255)
    phone_real : Optional[str]  = Field(None, max_length=20)
    is_active  : Optional[bool] = None


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

VALID_STATES = {s.upper() for s in ["VIC", "NSW", "QLD", "WA", "SA", "TAS", "NT", "ACT"]}

VALID_INSURANCE_TYPES = {
    InsuranceType.PUBLIC_LIABILITY,
    InsuranceType.WORKERS_COMPENSATION,
    InsuranceType.PROFESSIONAL_INDEMNITY,
}


async def _require_tradie_profile(user: User, db: AsyncSession) -> TradieProfile:
    res = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == user.id)
    )
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")
    return profile


async def _require_owner_of_business(profile: TradieProfile, member_id: str, db: AsyncSession) -> TeamMember:
    res = await db.execute(
        select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.business_id == profile.id,
        )
    )
    member = res.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Worker not found in your business")
    return member


def _cert_response(cert: TradieCertification) -> dict:
    return {
        "id":               cert.id,
        "category_id":      cert.category_id,
        "category_name":    cert.category.name if cert.category else None,
        "category_slug":    cert.category.slug if cert.category else None,
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
        "verified_at":      cert.verified_at,
        "team_member_id":   cert.team_member_id,
        "created_at":       cert.created_at,
    }


def _insurance_response(policy: InsurancePolicy) -> dict:
    return {
        "id":                     policy.id,
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
        "verified_at":            policy.verified_at,
        "created_at":             policy.created_at,
    }


def _worker_response(member: TeamMember) -> dict:
    return {
        "id":              member.id,
        "full_name":       member.full_name,
        "email":           member.email,
        "role":            member.role,
        "is_active":       member.is_active,
        "can_accept_jobs": member.can_accept_jobs,
        "avatar_url":      member.avatar_url,
        "selfie_url":      member.selfie_url,
        "jobs_completed":  member.jobs_completed,
        "no_show_count":   member.no_show_count,
        "rating_avg":      float(member.rating_avg) if member.rating_avg else None,
        "created_at":      member.created_at,
    }


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/onboarding/submit", status_code=201)
async def submit_onboarding(
    body: OnboardingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can submit onboarding.")

    if not current_user.is_verified:
        raise HTTPException(status_code=400, detail="Verify your email before continuing.")

    res = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You've already submitted onboarding.")

    abn_clean = body.abn.replace(" ", "").strip()
    if len(abn_clean) != 11 or not abn_clean.isdigit():
        raise HTTPException(status_code=400, detail="ABN must be 11 digits.")
    res = await db.execute(
        select(TradieProfile).where(TradieProfile.abn == abn_clean)
    )
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="This ABN is already registered. Contact support if this is an error.",
        )

    if body.solo_or_team == "team" and not body.team_size:
        raise HTTPException(status_code=400, detail="Please tell us your team size.")

    profile = TradieProfile(
        id                  = str(uuid.uuid4()),
        user_id             = current_user.id,
        business_name       = body.business_name.strip(),
        abn                 = abn_clean,
        suburb              = body.suburb.strip(),
        state               = body.state.strip().upper(),
        postcode            = body.postcode.strip(),
        bio                 = (body.bio or "").strip() or None,
        solo_or_team        = body.solo_or_team,
        team_size           = body.team_size if body.solo_or_team == "team" else None,
        verification_status = "pending_review",
        is_available        = False,
        radius_km           = body.radius_km,
        credits             = 0,
    )
    db.add(profile)

    if body.phone:
        current_user.phone = body.phone.strip()
        db.add(current_user)

    await db.flush()

    seen  = set()
    first = True
    for cat_id in body.category_ids:
        if cat_id in seen:
            continue
        seen.add(cat_id)
        cat_res = await db.execute(
            select(Category).where(Category.id == cat_id, Category.level == CategoryLevel.TRADE)
        )
        if not cat_res.scalar_one_or_none():
            continue
        link = TradieCategory(tradie_id=profile.id, category_id=cat_id, is_primary=first)
        db.add(link)
        first = False

    owner_member = TeamMember(
        id              = str(uuid.uuid4()),
        business_id     = profile.id,
        user_id         = current_user.id,
        full_name       = current_user.full_name,
        email           = current_user.email,
        phone_real      = (body.phone or "").strip() or (current_user.phone or ""),
        role            = TeamMemberRole.OWNER,
        hashed_password = None,
        is_active       = True,
        can_accept_jobs = False,
    )
    db.add(owner_member)

    try:
        lat, lng = await geocode_tradie_suburb(profile.suburb, profile.state)
        if lat:
            profile.lat = lat
            profile.lng = lng
            db.add(profile)
    except Exception as e:
        print(f"[onboarding] geocode failed for {profile.suburb}, {profile.state}: {e}")

    seed_suburb = {
        "suburb":     body.suburb.strip(),
        "state_code": body.state.strip().upper(),
        "postcode":   body.postcode.strip(),
        "label":      f"{body.suburb.strip()} ({body.state.strip().upper()} {body.postcode.strip()})",
    }
    preference = TradiePreference(
        tradie_id       = profile.id,
        service_suburbs = json.dumps([seed_suburb]),
        notify_email    = True,
        notify_sms      = False,
    )
    db.add(preference)

    await db.commit()
    await db.refresh(profile)

    return {
        "id":                  profile.id,
        "verification_status": profile.verification_status,
        "message":             "Onboarding submitted. We'll review and approve within 1 business day.",
        "next_steps": [
            "Submit your trade licence numbers under /certifications/submit",
            "Submit your public liability insurance under /insurance/submit",
            "Our team will verify and approve within 1 business day.",
        ],
    }


@router.get("/", response_model=TradieListResponse)
async def list_tradies(
    page:         int            = Query(1,    ge=1),
    limit:        int            = Query(10,   ge=1, le=50),
    category_id:  Optional[str]  = Query(None),
    suburb:       Optional[str]  = Query(None),
    state:        Optional[str]  = Query(None),
    is_available: Optional[bool] = Query(None),
    db:           AsyncSession   = Depends(get_db),
):
    query = (
        select(TradieProfile)
        .options(
            selectinload(TradieProfile.user),
            selectinload(TradieProfile.tradie_categories).selectinload(TradieCategory.category),
        )
    )
    if category_id:
        query = (
            query.join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id)
            .where(TradieCategory.category_id == category_id)
        )
    if suburb:
        query = query.where(TradieProfile.suburb.ilike(f"%{suburb}%"))
    if state:
        query = query.where(TradieProfile.state.ilike(f"%{state}%"))
    if is_available is not None:
        query = query.where(TradieProfile.is_available == is_available)

    count_query  = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total        = total_result.scalar() or 0

    offset = (page - 1) * limit
    query  = query.offset(offset).limit(limit).order_by(TradieProfile.created_at.desc())
    result  = await db.execute(query)
    tradies = result.scalars().unique().all()

    items = []
    for profile in tradies:
        categories = [
            CategoryBrief(id=tc.category.id, name=tc.category.name)
            for tc in profile.tradie_categories
            if tc.category is not None
        ]
        items.append(TradieListItem(
            id=profile.id,
            business_name=profile.business_name,
            bio=profile.bio,
            suburb=profile.suburb,
            state=profile.state,
            is_available=profile.is_available,
            avatar_url=profile.avatar_url,
            is_verified=profile.user.is_verified if profile.user else False,
            categories=categories,
        ))

    return TradieListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 1,
    )


@router.post("/profile", response_model=TradieProfileResponse, status_code=201)
async def create_profile(
    body: TradieProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can create a profile")
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Profile already exists")
    data = body.model_dump()
    if data.get("suburb") and not data.get("lat"):
        lat, lng = await geocode_tradie_suburb(data["suburb"], data.get("state"))
        data["lat"] = lat
        data["lng"] = lng
    profile = TradieProfile(id=str(uuid.uuid4()), user_id=current_user.id, **data)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.patch("/profile/me", response_model=TradieProfileResponse)
async def update_profile(
    body: TradieProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    if "suburb" in updates and "lat" not in updates:
        lat, lng = await geocode_tradie_suburb(profile.suburb, profile.state)
        if lat:
            profile.lat = lat
            profile.lng = lng
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/profile/me", response_model=TradieProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    response = profile.__dict__.copy()
    response["phone"] = current_user.phone or ""
    return response


@router.post("/{tradie_id}/inquiry", response_model=InquiryResponse, status_code=201)
async def send_inquiry(
    tradie_id:    str,
    body:         InquiryCreate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.user))
        .where(TradieProfile.id == tradie_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie not found")
    inquiry = Inquiry(
        id=str(uuid.uuid4()),
        tradie_id=tradie_id,
        sender_id=current_user.id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        message=body.message,
    )
    db.add(inquiry)
    await db.commit()
    await db.refresh(inquiry)
    try:
        await notify_tradie_new_inquiry(
            tradie_user_id=profile.user_id,
            tradie_name=profile.business_name,
            tradie_email=profile.user.email if profile.user else "",
            tradie_phone=profile.user.phone if profile.user else None,
            sender_name=body.name,
            sender_email=body.email,
            sender_phone=body.phone,
            message=body.message,
            inquiry_id=inquiry.id,
        )
    except Exception:
        pass
    return inquiry


@router.get("/{tradie_id}/public", response_model=TradiePublicResponse)
async def get_tradie_public_profile(
    tradie_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TradieProfile)
        .options(
            selectinload(TradieProfile.user),
            selectinload(TradieProfile.tradie_categories).selectinload(TradieCategory.category),
        )
        .where(TradieProfile.id == tradie_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie not found")

    # FIX 1: was "approved" — Django admin sets "verified", not "approved"
    if profile.verification_status != APPROVED_STATUS:
        raise HTTPException(status_code=404, detail="Tradie not found")

    categories = [
        CategoryBrief(id=tc.category.id, name=tc.category.name)
        for tc in profile.tradie_categories
        if tc.category is not None
    ]
    return TradiePublicResponse(
        id=profile.id,
        business_name=profile.business_name,
        bio=profile.bio,
        suburb=profile.suburb,
        state=profile.state,
        is_available=profile.is_available,
        avatar_url=profile.avatar_url,
        cover_photo_url=profile.cover_photo_url,
        is_verified=profile.user.is_verified if profile.user else False,
        full_name=profile.user.full_name if profile.user else None,
        categories=categories,
    )


@router.get("/stats/me")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.reviews))
        .where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    review_count = len(profile.reviews)
    avg_rating   = (
        round(sum(r.rating for r in profile.reviews) / review_count, 1)
        if review_count > 0 else 0.0
    )
    return {
        "avg_rating":   avg_rating,
        "review_count": review_count,
        "credits":      profile.credits,
        "is_available": profile.is_available,
    }


@router.get("/dashboard/me")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can access the dashboard")
    profile_result = await db.execute(
        select(TradieProfile)
        .options(selectinload(TradieProfile.reviews))
        .where(TradieProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")
    leads_result = await db.execute(
        select(Lead)
        .join(Job, Job.id == Lead.job_id)
        .options(selectinload(Lead.job))
        .where(
            Lead.tradie_id == profile.id,
            Job.is_deleted == False,
            Job.status != "cancelled",
        )
        .order_by(Lead.sent_at.desc())
    )
    leads               = leads_result.scalars().all()
    review_count        = len(profile.reviews)
    avg_rating          = (
        round(sum(r.rating for r in profile.reviews) / review_count, 1)
        if review_count > 0 else 0.0
    )
    total_leads         = len(leads)
    responded           = sum(1 for l in leads if l.status == "quoted")
    response_rate       = (
        round((responded / total_leads) * 100, 1) if total_leads > 0 else 0.0
    )
    total_credits_spent = sum(l.credits_charged for l in leads)

    lead_cards = []
    for lead in leads:
        job           = lead.job
        is_urgent     = (job.urgency in URGENT_VALUES         if job and job.urgency     else False)
        is_high_value = (job.budget_max >= HIGH_VALUE_THRESHOLD if job and job.budget_max else False)
        lead_cards.append(LeadResponse(
            id=lead.id,
            job_id=lead.job_id,
            tradie_id=lead.tradie_id,
            credits_charged=lead.credits_charged,
            status=lead.status,
            sent_at=lead.sent_at,
            job_title=job.title             if job else None,
            job_suburb=job.suburb           if job else None,
            job_state=job.state             if job else None,
            job_description=job.description if job else None,
            job_budget_min=job.budget_min   if job else None,
            job_budget_max=job.budget_max   if job else None,
            job_urgency=job.urgency         if job else None,
            job_type=job.job_type           if job else None,
            service_type=job.service_type   if job else None,
            job_stage=job.job_stage         if job else None,
            is_urgent=is_urgent,
            is_high_value=is_high_value,
            job_status=job.status if job else None,
        ))

    return {
        "stats": {
            "avg_rating":          avg_rating,
            "review_count":        review_count,
            "credits":             profile.credits,
            "total_leads":         total_leads,
            "response_rate":       response_rate,
            "total_credits_spent": total_credits_spent,
            "is_available":        profile.is_available,
        },
        "leads": lead_cards,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/onboarding/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)

    cert_res = await db.execute(
        select(TradieCertification)
        .options(selectinload(TradieCertification.category))
        .where(TradieCertification.tradie_profile_id == profile.id)
        .order_by(TradieCertification.created_at.desc())
    )
    certs = cert_res.scalars().all()

    ins_res = await db.execute(
        select(InsurancePolicy)
        .where(InsurancePolicy.tradie_profile_id == profile.id)
        .order_by(InsurancePolicy.created_at.desc())
    )
    policies = ins_res.scalars().all()

    member_res = await db.execute(
        select(TeamMember)
        .where(TeamMember.business_id == profile.id)
        .order_by(TeamMember.created_at)
    )
    members = member_res.scalars().all()

    member_list = []
    for m in members:
        m_cert_res = await db.execute(
            select(TradieCertification)
            .options(selectinload(TradieCertification.category))
            .where(TradieCertification.team_member_id == m.id)
        )
        m_certs = m_cert_res.scalars().all()
        member_list.append({
            **_worker_response(m),
            "certifications": [_cert_response(c) for c in m_certs],
        })

    has_verified_cert      = any(c.status == CertificationStatus.VERIFIED for c in certs)
    has_verified_insurance = any(
        p.status == InsuranceStatus.VERIFIED
        and p.insurance_type == InsuranceType.PUBLIC_LIABILITY
        for p in policies
    )

    # FIX 2 & 3: was "approved" — Django admin sets "verified", not "approved"
    profile_verified      = profile.verification_status == APPROVED_STATUS
    ready_to_receive_jobs = (
        profile_verified
        and has_verified_cert
        and has_verified_insurance
    )

    return {
        "profile": {
            "id":                  profile.id,
            "business_name":       profile.business_name,
            "verification_status": profile.verification_status,
            "verification_notes":  profile.verification_notes,
            "is_available":        profile.is_available,
            "solo_or_team":        profile.solo_or_team,
        },
        "certifications":     [_cert_response(c) for c in certs],
        "insurance_policies": [_insurance_response(p) for p in policies],
        "team_members":       member_list,
        "gates": {
            "profile_approved":       profile_verified,          # True when verification_status == "verified"
            "has_verified_cert":      has_verified_cert,
            "has_verified_insurance": has_verified_insurance,
            "ready_to_receive_jobs":  ready_to_receive_jobs,
        },
    }


@router.get("/categories/tree")
async def get_category_tree(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Category)
        .options(
            selectinload(Category.children).selectinload(Category.children),
            selectinload(Category.service_questions),
        )
        .where(Category.is_active == True, Category.level == CategoryLevel.TRADE)
        .order_by(Category.name)
    )
    top_level = res.scalars().unique().all()

    def format_question(q: ServiceQuestion) -> dict:
        return {
            "id":          q.id,
            "question":    q.question_text,
            "answer_type": q.answer_type,
            "options":     q.options,
            "placeholder": q.placeholder,
            "is_required": q.is_required,
            "sort_order":  q.sort_order,
        }

    def format_task(task: Category) -> dict:
        return {"id": task.id, "name": task.name, "slug": task.slug, "description": task.description}

    def format_subcat(sub: Category) -> dict:
        return {
            "id":          sub.id,
            "name":        sub.name,
            "slug":        sub.slug,
            "description": sub.description,
            "questions":   [format_question(q) for q in sorted(sub.service_questions, key=lambda q: q.sort_order)],
            "tasks":       [format_task(t) for t in sub.children if t.is_active],
        }

    tree = []
    for cat in top_level:
        tree.append({
            "id":            cat.id,
            "name":          cat.name,
            "slug":          cat.slug,
            "icon_slug":     cat.icon_slug,
            "description":   cat.description,
            "subcategories": [format_subcat(s) for s in cat.children if s.is_active],
        })

    return {"categories": tree}


# ── Certifications ────────────────────────────────────────────────────────

@router.post("/certifications/submit", status_code=201)
async def submit_certification(
    body: CertificationSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)

    cat_res = await db.execute(
        select(Category).where(
            Category.id == body.category_id,
            Category.level == CategoryLevel.TRADE,
            Category.is_active == True,
        )
    )
    category = cat_res.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=400, detail="category_id must be a valid active level-1 trade category.")
    canonical_category = await resolve_to_canonical_trade(db, category)
    if not canonical_category:
        raise HTTPException(status_code=400, detail="category_id must resolve to a valid trade category.")
    category_id = canonical_category.id

    state_upper = body.issuing_state.upper()
    if state_upper not in VALID_STATES:
        raise HTTPException(status_code=400, detail=f"issuing_state must be one of: {', '.join(sorted(VALID_STATES))}")

    if body.expires_at and body.expires_at <= date.today():
        raise HTTPException(status_code=400, detail="Licence has already expired. Submit a current licence.")

    tradie_profile_id = None
    team_member_id    = None

    if body.team_member_id:
        member = await _require_owner_of_business(profile, body.team_member_id, db)
        team_member_id = member.id
    else:
        tradie_profile_id = profile.id

    existing_q = select(TradieCertification).where(
        TradieCertification.category_id == category_id,
        TradieCertification.status.in_([CertificationStatus.PENDING, CertificationStatus.IN_REVIEW]),
    )
    if tradie_profile_id:
        existing_q = existing_q.where(TradieCertification.tradie_profile_id == tradie_profile_id)
    else:
        existing_q = existing_q.where(TradieCertification.team_member_id == team_member_id)

    existing_res = await db.execute(existing_q)
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A pending certification for this category already exists.")

    cert = TradieCertification(
        id                = str(uuid.uuid4()),
        tradie_profile_id = tradie_profile_id,
        team_member_id    = team_member_id,
        category_id       = category_id,
        licence_number    = body.licence_number.strip().upper(),
        issuing_state     = state_upper,
        issuing_body      = (body.issuing_body or "").strip() or None,
        holder_name       = body.holder_name.strip(),
        issued_at         = body.issued_at,
        expires_at        = body.expires_at,
        photo_url         = body.photo_url,
        status            = CertificationStatus.PENDING,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)

    return {
        "id":      cert.id,
        "status":  cert.status,
        "message": "Licence submitted for admin verification. You'll receive an email when reviewed.",
    }


@router.get("/certifications/me")
async def get_my_certifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(TradieCertification)
        .options(selectinload(TradieCertification.category))
        .where(TradieCertification.tradie_profile_id == profile.id)
        .order_by(TradieCertification.created_at.desc())
    )
    certs = res.scalars().all()
    return {"certifications": [_cert_response(c) for c in certs]}


@router.delete("/certifications/{cert_id}", status_code=204)
async def delete_certification(
    cert_id:      str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(TradieCertification).where(
            TradieCertification.id == cert_id,
            TradieCertification.tradie_profile_id == profile.id,
        )
    )
    cert = res.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    if cert.status == CertificationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Verified certifications cannot be deleted. Contact support.")
    await db.delete(cert)
    await db.commit()


# ── Insurance ─────────────────────────────────────────────────────────────

@router.post("/insurance/submit", status_code=201)
async def submit_insurance(
    body: InsurancePolicySubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)

    if body.insurance_type not in VALID_INSURANCE_TYPES:
        raise HTTPException(status_code=400, detail=f"insurance_type must be one of: {', '.join(VALID_INSURANCE_TYPES)}")

    if body.expires_at <= date.today():
        raise HTTPException(status_code=400, detail="Insurance policy has already expired. Submit a current policy.")

    existing_res = await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.tradie_profile_id == profile.id,
            InsurancePolicy.insurance_type    == body.insurance_type,
            InsurancePolicy.status.in_([InsuranceStatus.PENDING, InsuranceStatus.IN_REVIEW]),
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"A pending {body.insurance_type} policy already exists.")

    policy = InsurancePolicy(
        id                    = str(uuid.uuid4()),
        tradie_profile_id     = profile.id,
        insurance_type        = body.insurance_type,
        insurer_name          = body.insurer_name.strip(),
        policy_number         = body.policy_number.strip().upper(),
        coverage_amount_cents = body.coverage_amount_cents,
        holder_name           = body.holder_name.strip(),
        issued_at             = body.issued_at,
        expires_at            = body.expires_at,
        document_url          = body.document_url,
        status                = InsuranceStatus.PENDING,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    return {
        "id":      policy.id,
        "status":  policy.status,
        "message": "Insurance policy submitted for admin verification. You'll receive an email when reviewed.",
    }


@router.get("/insurance/me")
async def get_my_insurance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(InsurancePolicy)
        .where(InsurancePolicy.tradie_profile_id == profile.id)
        .order_by(InsurancePolicy.created_at.desc())
    )
    policies = res.scalars().all()
    return {"insurance_policies": [_insurance_response(p) for p in policies]}


@router.delete("/insurance/{policy_id}", status_code=204)
async def delete_insurance(
    policy_id:    str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.id                == policy_id,
            InsurancePolicy.tradie_profile_id == profile.id,
        )
    )
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Insurance policy not found")
    if policy.status == InsuranceStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Verified insurance policies cannot be deleted. Contact support.")
    await db.delete(policy)
    await db.commit()


# ── Edit request endpoints ────────────────────────────────────────────────

class EditRequestBody(BaseModel):
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for requesting an edit")


@router.post("/certifications/{cert_id}/request-edit", status_code=200)
async def request_cert_edit(
    cert_id: str,
    body: EditRequestBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tradie requests permission to edit a submitted/verified certification."""
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(TradieCertification).where(
            TradieCertification.id == cert_id,
            TradieCertification.tradie_profile_id == profile.id,
        )
    )
    cert = res.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found.")

    # Store the request note — admin sees this in the panel
    cert.edit_request_note = body.reason.strip()
    db.add(cert)
    await db.commit()

    # Notify admin via email if SendGrid configured
    await _send_edit_request_email(
        doc_type="Licence",
        doc_ref=cert.licence_number,
        tradie_name=profile.business_name or current_user.email,
        tradie_email=current_user.email,
        reason=body.reason.strip(),
    )

    return {"message": "Edit request sent to admin. You'll be notified once reviewed."}


@router.post("/insurance/{policy_id}/request-edit", status_code=200)
async def request_insurance_edit(
    policy_id: str,
    body: EditRequestBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tradie requests permission to edit a submitted/verified insurance policy."""
    profile = await _require_tradie_profile(current_user, db)
    res = await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.id == policy_id,
            InsurancePolicy.tradie_profile_id == profile.id,
        )
    )
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Insurance policy not found.")

    policy.edit_request_note = body.reason.strip()
    db.add(policy)
    await db.commit()

    await _send_edit_request_email(
        doc_type="Insurance Policy",
        doc_ref=policy.policy_number,
        tradie_name=profile.business_name or current_user.email,
        tradie_email=current_user.email,
        reason=body.reason.strip(),
    )

    return {"message": "Edit request sent to admin. You'll be notified once reviewed."}


async def _send_edit_request_email(
    doc_type: str,
    doc_ref: str,
    tradie_name: str,
    tradie_email: str,
    reason: str,
) -> None:
    """Notify admin that a tradie has requested to edit a document."""
    import logging
    logger = logging.getLogger(__name__)
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@proconnect.com.au")

    if not SENDGRID_API_KEY:
        logger.info(f"[Edit Request] {tradie_name} ({tradie_email}) wants to edit {doc_type} #{doc_ref}. Reason: {reason}")
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        body_text = (
            f"Edit Request — {doc_type}\n\n"
            f"Tradie:     {tradie_name}\n"
            f"Email:      {tradie_email}\n"
            f"Document:   {doc_type} — {doc_ref}\n\n"
            f"Reason for edit:\n{reason}\n\n"
            f"Please review this in the admin panel and unlock the document if approved."
        )
        mail = Mail(
            from_email="noreply@proconnect.com.au",
            to_emails=ADMIN_EMAIL,
            subject=f"[Edit Request] {tradie_name} — {doc_type} #{doc_ref}",
            plain_text_content=body_text,
        )
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        sg.send(mail)
    except Exception as e:
        logger.error(f"Failed to send edit-request email: {e}")


# ── Availability toggle ───────────────────────────────────────────────────

@router.patch("/availability/toggle")
async def toggle_availability(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    profile = await _require_tradie_profile(current_user, db)

    # FIX 4: was "approved" — Django admin sets "verified", not "approved"
    if profile.verification_status != APPROVED_STATUS:
        raise HTTPException(
            status_code=403,
            detail="Your account must be approved before you can accept bookings.",
        )

    new_state            = not profile.is_available
    profile.is_available = new_state
    db.add(profile)
    await db.commit()

    cache_key = f"availability:tradie:{profile.id}"
    try:
        await redis.delete(cache_key)
    except Exception as e:
        print(f"[availability:toggle] Redis delete failed for {cache_key}: {e}")
    finally:
        await redis.aclose()

    return {
        "is_available": new_state,
        "message":      "Bookings resumed." if new_state else "Bookings paused. You won't receive new leads.",
    }


# ── Team worker management ────────────────────────────────────────────────

@router.post("/team/workers", status_code=201)
async def add_worker(
    body: WorkerInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can manage team members.")

    profile = await _require_tradie_profile(current_user, db)

    if profile.solo_or_team != "team":
        raise HTTPException(status_code=400, detail="Your account is set to solo. Update your profile to 'team' first.")

    existing = await db.execute(
        select(TeamMember).where(TeamMember.email == body.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A worker with this email already exists.")

    member = TeamMember(
        id              = str(uuid.uuid4()),
        business_id     = profile.id,
        user_id         = None,
        full_name       = body.full_name.strip(),
        email           = body.email.lower().strip(),
        phone_real      = body.phone_real.strip(),
        role            = TeamMemberRole.WORKER,
        hashed_password = _bcrypt.hashpw(body.password[:72].encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8"),
        is_active       = True,
        can_accept_jobs = False,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return {
        **_worker_response(member),
        "message": f"Worker {member.full_name} added. They must complete licence verification before accepting jobs.",
    }


@router.get("/team/workers")
async def list_workers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)

    res = await db.execute(
        select(TeamMember)
        .where(TeamMember.business_id == profile.id)
        .order_by(TeamMember.role.desc(), TeamMember.created_at)
    )
    members = res.scalars().all()

    result = []
    for m in members:
        cert_res = await db.execute(
            select(TradieCertification)
            .options(selectinload(TradieCertification.category))
            .where(TradieCertification.team_member_id == m.id)
        )
        certs = cert_res.scalars().all()
        result.append({
            **_worker_response(m),
            "certifications": [_cert_response(c) for c in certs],
        })

    return {"workers": result, "total": len(result)}


@router.patch("/team/workers/{member_id}")
async def update_worker(
    member_id:    str,
    body:         WorkerUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    member  = await _require_owner_of_business(profile, member_id, db)

    if body.full_name is not None:
        member.full_name  = body.full_name.strip()
    if body.phone_real is not None:
        member.phone_real = body.phone_real.strip()
    if body.is_active is not None:
        member.is_active = body.is_active
        if not body.is_active:
            member.can_accept_jobs = False

    member.updated_at = datetime.utcnow()
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return {**_worker_response(member), "message": "Worker updated."}


@router.delete("/team/workers/{member_id}", status_code=200)
async def deactivate_worker(
    member_id:    str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _require_tradie_profile(current_user, db)
    member  = await _require_owner_of_business(profile, member_id, db)

    if member.role == TeamMemberRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot deactivate the business owner.")

    member.is_active       = False
    member.can_accept_jobs = False
    member.updated_at      = datetime.utcnow()
    db.add(member)
    await db.commit()

    return {
        "id":      member.id,
        "message": f"{member.full_name} has been deactivated and will no longer receive job assignments.",
    }
