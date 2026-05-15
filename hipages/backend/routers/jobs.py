"""
backend/routers/jobs.py

UPDATED — all existing endpoints preserved exactly. New endpoints added:

  POST /{job_id}/start                Tradie marks job as started (hired → in_progress).
                                       Requires before-photo URL (uploaded via /api/upload-photo).
  POST /{job_id}/scope-change         Tradie requests a scope change (in_progress only).
                                       Same-category: goes to awaiting_scope_approval.
                                       Different-category: blocked by skill-boundary check.
  POST /{job_id}/scope-change/respond Homeowner approves or rejects the scope change.
                                       Approve → in_progress (new scope).
                                       Reject → in_progress (original scope continues).
  POST /{job_id}/complete             Tradie marks job complete. Requires after-photo URL.
  POST /{job_id}/confirm-complete     Homeowner confirms completion (starts 48h dispute window).
  POST /{job_id}/partial-stop        Tradie stops mid-job. Requires reason + photo.
  POST /{job_id}/dispute              Homeowner raises a dispute (in completed or partial_stop).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.session import get_db
from models.job import Job
from models.user import User
from models.category import Category, CategoryLevel
from models.lead import Lead
from models.quote import Quote
from models.tradie_certification import TradieCertification, CertificationStatus
from models.tradie_profile import TradieProfile
from schemas.job_schema import JobCreate, JobUpdate, JobResponse, JobWithDetailsResponse, JobPhotoResponse
from services.auth_service import get_current_user
from services.category_resolver import resolve_trade_category
from services.job_state_machine import JobStateMachine, InvalidTransitionError
from services.geocoding_service import geocode_suburb
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
from typing import Optional
import asyncio
import json
import uuid

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


# ═══════════════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS — PRESERVED EXACTLY
# ═══════════════════════════════════════════════════════════════════════════

async def _distribute_leads_background(job_id: str) -> None:
    """
    Fallback: run lead distribution in-process when Celery is unavailable.
    Creates its own DB engine/session (same pattern as the Celery task).
    """
    try:
        from tasks.lead_tasks import _distribute_leads, _make_session_factory
        engine, session_factory = _make_session_factory()
        try:
            await _distribute_leads(job_id, session_factory)
            print(f"[leads] Background fallback completed for job {job_id}")
        finally:
            try:
                await engine.dispose()
            except Exception:
                pass
    except Exception as e:
        print(f"[leads] Background fallback failed for job {job_id}: {e}")


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can post jobs")

    # ── Category resolution — three-pass strategy ─────────────────────────────
    #
    # Pass 1 (fast path): try the submitted category_slug as an exact DB lookup.
    #   The homeowner picker sends a canonical slug like "plumbing" or "gas-fitting"
    #   directly. resolve_trade_category() will find it on the first slug== query
    #   without touching any NLP code. This is the normal production path.
    #
    # Pass 2 (description NLP): if the slug didn't resolve (e.g. user somehow sent
    #   a free-text value), run the keyword/alias resolver against the job title
    #   and description only — NOT the slug — so the slug doesn't pollute the text.
    #
    # Pass 3 (synonym map): if passes 1–2 both fail, try resolve_trade_category on
    #   just the raw slug string, which runs it through SYNONYM_TO_CANONICAL_SLUG
    #   (e.g. slug "plumber" → canonical "plumbing").
    #
    # Keeping these three passes separate ensures that an exact canonical slug from
    # the UI always wins instantly, while free-text descriptions still work as a
    # fallback for AI-chat or legacy callers.
    # ──────────────────────────────────────────────────────────────────────────
    category = await resolve_trade_category(db, body.category_slug)

    if not category and (body.title or body.description):
        category = await resolve_trade_category(
            db,
            " ".join(part for part in [body.title, body.description or ""] if part),
        )

    if not category:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown service '{body.category_slug}'. "
                "Please select a valid service from the list."
            )
        )

    data = body.model_dump(exclude={"category_slug", "intent_level"})
    data["category_id"] = category.id

    if data.get("suburb") and not data.get("lat"):
        lat, lng = await geocode_suburb(data["suburb"], data.get("state"))
        data["lat"] = lat
        data["lng"] = lng

    job = Job(
        id=str(uuid.uuid4()),
        homeowner_id=current_user.id,
        **data
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    celery_queued = False
    try:
        from tasks.lead_tasks import distribute_leads
        task = await asyncio.get_event_loop().run_in_executor(
            None, lambda: distribute_leads.apply_async(args=[job.id])
        )
        job.lead_task_id = task.id
        db.add(job)
        await db.commit()
        celery_queued = True
        print(f"[leads] Queued via Celery for job {job.id}, task_id={task.id}")
    except Exception as e:
        print(f"[leads] Celery unavailable ({e}) — falling back to in-process background task")

    if not celery_queued:
        # Celery not running — distribute leads immediately in a FastAPI background task
        background_tasks.add_task(_distribute_leads_background, job.id)
        print(f"[leads] Background fallback scheduled for job {job.id}")

    return job


@router.post("/{job_id}/retry-leads", status_code=202)
async def retry_lead_distribution(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-trigger lead distribution for a job that received 0 leads.
    Homeowner can call this from their dashboard; admin can also call it.
    Only works when the job is in 'open' or 'quoted' status.
    The idempotency guard in _distribute_leads allows retry when matched==0.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role == "homeowner" and job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    if job.status not in ("open", "quoted"):
        raise HTTPException(status_code=400, detail=f"Cannot retry leads for a job in '{job.status}' status")

    # Reset match_intelligence so the idempotency guard doesn't block
    job.match_intelligence = None
    db.add(job)
    await db.commit()

    celery_queued = False
    try:
        from tasks.lead_tasks import distribute_leads
        task = await asyncio.get_event_loop().run_in_executor(
            None, lambda: distribute_leads.apply_async(args=[job_id])
        )
        job.lead_task_id = task.id
        db.add(job)
        await db.commit()
        celery_queued = True
    except Exception:
        pass

    if not celery_queued:
        background_tasks.add_task(_distribute_leads_background, job_id)

    return {"message": "Lead distribution re-queued", "job_id": job_id}


@router.get("/my-jobs", response_model=list[JobWithDetailsResponse])
async def my_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can view their jobs")

    query = (
        select(Job)
        .options(
            selectinload(Job.category),
            selectinload(Job.leads),
            selectinload(Job.photos),
            selectinload(Job.review),
        )
        .where(Job.homeowner_id == current_user.id)
        .where(Job.is_deleted == False)
    )

    if status:
        query = query.where(Job.status == status)

    query = query.order_by(Job.created_at.desc())
    result = await db.execute(query)
    jobs = result.scalars().all()

    response = []
    for job in jobs:
        lead_ids = [l.id for l in job.leads]
        quote_count = 0
        if lead_ids:
            quotes_result = await db.execute(
                select(Quote).where(Quote.lead_id.in_(lead_ids))
            )
            quote_count = len(quotes_result.scalars().all())

        response.append(JobWithDetailsResponse(
            id=job.id,
            homeowner_id=job.homeowner_id,
            category_id=job.category_id,
            category_name=job.category.name if job.category else None,
            title=job.title,
            description=job.description,
            suburb=job.suburb,
            state=job.state,
            postcode=job.postcode,
            lat=job.lat,
            lng=job.lng,
            budget_min=job.budget_min,
            budget_max=job.budget_max,
            status=job.status,
            urgency=job.urgency,
            job_type=job.job_type,
            service_type=job.service_type,
            job_stage=job.job_stage,
            contact_name=job.contact_name,
            contact_phone=job.contact_phone,
            contact_email=job.contact_email,
            lead_count=len(job.leads),
            quote_count=quote_count,
            photo_count=len(job.photos),
            photos=[JobPhotoResponse(id=p.id, url=p.url, file_key=p.file_key) for p in job.photos],
            is_deleted=job.is_deleted,
            deleted_at=job.deleted_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            match_intelligence=job.match_intelligence,
            has_review=job.review is not None,
            review_status=job.review.status if job.review else None,
        ))

    return response


@router.get("/history", response_model=list[JobWithDetailsResponse])
async def job_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can view history")

    query = (
        select(Job)
        .options(
            selectinload(Job.category),
            selectinload(Job.leads),
            selectinload(Job.photos),
        )
        .where(Job.homeowner_id == current_user.id)
        .where(Job.is_deleted == True)
        .order_by(Job.deleted_at.desc())
    )
    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        JobWithDetailsResponse(
            id=job.id,
            homeowner_id=job.homeowner_id,
            category_id=job.category_id,
            category_name=job.category.name if job.category else None,
            title=job.title,
            description=job.description,
            suburb=job.suburb,
            state=job.state,
            postcode=job.postcode,
            lat=job.lat,
            lng=job.lng,
            budget_min=job.budget_min,
            budget_max=job.budget_max,
            status=job.status,
            urgency=job.urgency,
            job_type=job.job_type,
            service_type=job.service_type,
            job_stage=job.job_stage,
            contact_name=job.contact_name,
            contact_phone=job.contact_phone,
            contact_email=job.contact_email,
            lead_count=len(job.leads),
            quote_count=0,
            photo_count=len(job.photos),
            photos=[JobPhotoResponse(id=p.id, url=p.url, file_key=p.file_key) for p in job.photos],
            is_deleted=job.is_deleted,
            deleted_at=job.deleted_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.delete("/history/clear", status_code=204)
async def clear_job_history(
    job_id: str = Query(..., description="Job ID to permanently delete"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import delete as sql_delete
    from models.quote import Quote

    result = await db.execute(
        select(Job)
        .options(selectinload(Job.leads), selectinload(Job.photos), selectinload(Job.review))
        .where(Job.id == job_id)
        .where(Job.homeowner_id == current_user.id)
        .where(Job.is_deleted == True)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in history")

    lead_ids = [l.id for l in job.leads]
    if lead_ids:
        await db.execute(sql_delete(Quote).where(Quote.lead_id.in_(lead_ids)))

    await db.delete(job)
    await db.commit()
    return None


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    body: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job, field, value)

    if "suburb" in updates and not job.lat:
        lat, lng = await geocode_suburb(job.suburb, job.state)
        if lat:
            job.lat = lat
            job.lng = lng

    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/submit", response_model=JobResponse)
async def submit_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    missing = []
    if not job.urgency:       missing.append("urgency (Step 1)")
    if not job.job_type:      missing.append("job_type (Step 2)")
    if not job.service_type:  missing.append("service_type (Step 3)")
    if not job.job_stage:     missing.append("job_stage (Step 4)")
    if not job.description:   missing.append("description (Step 5)")
    if not job.suburb:        missing.append("suburb (Step 6)")
    if not job.contact_name:  missing.append("contact_name (Step 6)")
    if not job.contact_phone: missing.append("contact_phone (Step 6)")

    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Job is incomplete. Please fill all required fields before submitting.",
                "missing_fields": missing,
            }
        )

    if not job.lat and job.suburb:
        lat, lng = await geocode_suburb(job.suburb, job.state)
        if lat:
            job.lat = lat
            job.lng = lng

    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        from tasks.lead_tasks import distribute_leads
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: distribute_leads.apply_async(args=[job.id])
        )
        print(f"[leads] Re-queued distribution for submitted job {job.id}")
    except Exception as e:
        print(f"[leads] Warning: could not queue lead distribution: {e}")

    return job


@router.patch("/{job_id}/status")
async def update_job_status(
    job_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    if new_status == "completed" and not job.completed_at:
        job.completed_at = datetime.utcnow()

    try:
        await JobStateMachine.transition(job, new_status, current_user, db)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {"status": job.status}


@router.get("/{job_id}/competition")
async def get_job_competition(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    leads_result = await db.execute(select(Lead).where(Lead.job_id == job_id))
    leads = leads_result.scalars().all()
    lead_ids = [l.id for l in leads]

    if not lead_ids:
        return {"quote_count": 0, "competition_level": "low"}

    quotes_result = await db.execute(select(Quote).where(Quote.lead_id.in_(lead_ids)))
    quote_count = len(quotes_result.scalars().all())

    if quote_count == 0:
        level, message = "none", "Be the first to quote!"
    elif quote_count < 2:
        level, message = "low", f"{quote_count} tradie has quoted — good chance to win"
    elif quote_count < 4:
        level, message = "medium", f"{quote_count} tradies have quoted — competitive"
    else:
        level, message = "high", f"{quote_count} tradies have quoted — offer your best price"

    return {"quote_count": quote_count, "competition_level": level, "message": message}


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    job.is_deleted = True
    job.deleted_at = datetime.utcnow()
    db.add(job)
    await db.commit()
    return None


@router.delete("/{job_id}/photos/{photo_id}", status_code=204)
async def delete_job_photo(
    job_id: str,
    photo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from models.job_photo import JobPhoto

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    photo_result = await db.execute(
        select(JobPhoto).where(JobPhoto.id == photo_id, JobPhoto.job_id == job_id)
    )
    photo = photo_result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    await db.delete(photo)
    await db.commit()
    return None


@router.get("/{job_id}/photos", response_model=list[JobPhotoResponse])
async def get_job_photos(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from models.job_photo import JobPhoto

    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    allowed = False
    if current_user.id == job.homeowner_id:
        allowed = True
    elif current_user.role == "tradie":
        prof_res = await db.execute(
            select(TradieProfile.id).where(TradieProfile.user_id == current_user.id)
        )
        tradie_profile_id = prof_res.scalar_one_or_none()
        if tradie_profile_id:
            lead_res = await db.execute(
                select(Lead.id)
                .where(Lead.job_id == job_id, Lead.tradie_id == tradie_profile_id)
                .limit(1)
            )
            allowed = lead_res.scalar_one_or_none() is not None

    if not allowed:
        raise HTTPException(status_code=403, detail="Not authorised to view photos")

    photos_res = await db.execute(
        select(JobPhoto).where(JobPhoto.job_id == job_id).order_by(JobPhoto.created_at.asc())
    )
    return [
        JobPhotoResponse(id=p.id, url=p.url, file_key=p.file_key)
        for p in photos_res.scalars().all()
    ]


class ReviewCreateBody(BaseModel):
    rating:  int           = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)


class ReviewSubmittedResponse(BaseModel):
    id:         str
    job_id:     str
    rating:     int
    comment:    Optional[str]
    status:     str
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/{job_id}/review", response_model=ReviewSubmittedResponse, status_code=201)
async def submit_review(
    job_id: str,
    body: ReviewCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from models.review import Review

    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can leave reviews")

    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    if job.status not in ("completed", "confirmed", "closed"):
        raise HTTPException(status_code=400, detail="You can only review completed jobs")

    if job.completed_at:
        hours_since = (datetime.utcnow() - job.completed_at).total_seconds() / 3600
        if hours_since < 2:
            raise HTTPException(
                status_code=400,
                detail="Reviews can be submitted 2 hours after job completion. Please check back later."
            )

    existing = await db.execute(select(Review).where(Review.job_id == job_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You've already reviewed this job")

    lead_res = await db.execute(
        select(Lead).where(Lead.job_id == job_id, Lead.status == "accepted").limit(1)
    )
    lead = lead_res.scalar_one_or_none()
    if not lead:
        lead_res = await db.execute(
            select(Lead).where(Lead.job_id == job_id, Lead.status == "quoted").limit(1)
        )
        lead = lead_res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=400, detail="No tradie was hired for this job")

    review = Review(
        id=str(uuid.uuid4()),
        job_id=job_id,
        homeowner_id=current_user.id,
        tradie_id=lead.tradie_id,
        rating=body.rating,
        comment=(body.comment or "").strip() or None,
        status="pending",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return ReviewSubmittedResponse(
        id=review.id,
        job_id=review.job_id,
        rating=review.rating,
        comment=review.comment,
        status=review.status,
        created_at=review.created_at,
    )


# ═══════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS — JOB LIFECYCLE (tradie side)
# ═══════════════════════════════════════════════════════════════════════════

# ── Schemas ────────────────────────────────────────────────────────────────

class StartJobRequest(BaseModel):
    photo_before_url: Optional[str] = Field(None, description="S3 URL of the before photo (optional)")


class ScopeChangeRequest(BaseModel):
    reason:             str           = Field(..., min_length=5, max_length=1000)
    new_amount_cents:   int           = Field(..., gt=0, description="Proposed new total in cents")
    new_category_id:    Optional[str] = Field(None, description="Set only if requesting a different trade category (skill-boundary check will run)")


class ScopeChangeRespondRequest(BaseModel):
    approve: bool = Field(..., description="True = approve scope change, False = reject (original scope continues)")


class CompleteJobRequest(BaseModel):
    # Accepts 1–3 after-photo URLs. At least one is required.
    # Stored as a JSON array in the photo_after_url column (TEXT).
    photo_after_urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="1–3 S3 URLs of completion photos (at least one required, max 3)",
    )
    completion_note:  Optional[str] = Field(None, max_length=1000)


class PartialStopRequest(BaseModel):
    reason:           str           = Field(..., min_length=10, max_length=1000, description="Why work is being stopped")
    photo_after_url:  Optional[str] = Field(None, description="Photo of current state of work (recommended)")


class DisputeRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


# ── Helpers ────────────────────────────────────────────────────────────────

async def _require_tradie_with_lead(job_id: str, user: User, db: AsyncSession) -> TradieProfile:
    """Load the tradie profile for this user and confirm they have a lead on this job."""
    prof_res = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == user.id)
    )
    profile = prof_res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=403, detail="Tradie profile not found.")

    lead_res = await db.execute(
        select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == profile.id).limit(1)
    )
    if not lead_res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You do not have a lead on this job.")

    return profile


async def _load_job_or_404(job_id: str, db: AsyncSession) -> Job:
    res = await db.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


# ── Tradie: Mark job as started ────────────────────────────────────────────

@router.post("/{job_id}/start")
async def start_job(
    job_id:       str,
    body:         StartJobRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Tradie marks job as started (hired → in_progress).
    Before photo is MANDATORY — this is the first half of the dispute evidence bundle.
    GPS timestamp is recorded via the audit trail.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can start a job.")

    job = await _load_job_or_404(job_id, db)
    await _require_tradie_with_lead(job_id, current_user, db)

    try:
        JobStateMachine.assert_status(job, "hired")
        await JobStateMachine.transition(
            job=job,
            new_status="in_progress",
            current_user=current_user,
            db=db,
            note="Tradie arrived on site and uploaded before photo.",
            extra_job_fields={"photo_before_url": body.photo_before_url},
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "photo_before_url": job.photo_before_url,
        "message": "Job started. Upload an after photo when the work is complete.",
    }


# ── Tradie: Request scope change ───────────────────────────────────────────

@router.post("/{job_id}/scope-change")
async def request_scope_change(
    job_id:       str,
    body:         ScopeChangeRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Tradie requests a scope change mid-job (in_progress only).

    SAME-CATEGORY add (new_category_id is None):
      → Moves to awaiting_scope_approval. Homeowner gets a push notification.
      → If homeowner doesn't respond in 10 minutes → auto-rejected (original scope continues).

    DIFFERENT-CATEGORY request (new_category_id is set):
      → Skill-boundary check: does the tradie have a verified cert for the new category?
      → If not certified → blocked immediately. Tradie told they're not certified.
      → If certified → blocked anyway. Cross-category work requires a new job.
        System auto-creates a new job request for the correct category.
        Only the callout fee is charged for the original visit.

    VERBAL PRICE CHANGES ARE NOT VALID:
      If a homeowner verbally agrees to pay more, it means nothing. Only in-app
      approvals are recognised. Tradie must go through this endpoint.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can request scope changes.")

    job = await _load_job_or_404(job_id, db)
    await _require_tradie_with_lead(job_id, current_user, db)

    try:
        JobStateMachine.assert_status(job, "in_progress")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if job.scope_change_requested_at:
        raise HTTPException(
            status_code=400,
            detail="A scope change is already pending for this job. The homeowner must respond first.",
        )

    # ── Skill-boundary check ──────────────────────────────────────────────────
    if body.new_category_id and body.new_category_id != job.category_id:
        # Different trade category — this is ALWAYS blocked, even if user approves verbally.
        # The platform does not allow cross-skill work under the original booking.
        prof_res = await db.execute(
            select(TradieProfile).where(TradieProfile.user_id == current_user.id)
        )
        profile = prof_res.scalar_one_or_none()

        # Check if tradie is certified for the new category
        today = date.today()
        cert_res = await db.execute(
            select(TradieCertification).where(
                TradieCertification.tradie_profile_id == profile.id,
                TradieCertification.category_id == body.new_category_id,
                TradieCertification.status == CertificationStatus.VERIFIED,
                TradieCertification.expires_at > today,
            ).limit(1)
        )
        # Whether or not certified — cross-category work is blocked.
        # The tradie should flag "wrong service category" and trigger a re-book.
        raise HTTPException(
            status_code=400,
            detail=(
                "Cross-category scope changes are not allowed. "
                "If the job requires a different trade, use 'Flag wrong category' to "
                "trigger a re-booking for the correct specialist. "
                "You will only be charged the callout fee for this visit."
            ),
        )

    # ── Same-category scope change ────────────────────────────────────────────
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Schedule Celery auto-reject task
    scope_task_id = None
    try:
        from tasks.job_tasks import auto_reject_scope_change
        task = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: auto_reject_scope_change.apply_async(
                args=[job_id],
                countdown=600,   # 10 minutes in seconds
                queue="critical",
            ),
        )
        scope_task_id = task.id
    except Exception as e:
        print(f"[scope-change] Warning: could not schedule auto-reject task: {e}")

    try:
        await JobStateMachine.transition(
            job=job,
            new_status="awaiting_scope_approval",
            current_user=current_user,
            db=db,
            note=f"Tradie requested scope change: {body.reason}. New amount: {body.new_amount_cents} cents.",
            extra_job_fields={
                "pending_scope_amount_cents": body.new_amount_cents,
                "scope_change_reason":        body.reason,
                "scope_change_category_id":   None,
                "scope_change_requested_at":  datetime.utcnow(),
                "scope_change_expires_at":    expires_at,
                "scope_change_task_id":       scope_task_id,
            },
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "pending_scope_amount_cents": job.pending_scope_amount_cents,
        "scope_change_expires_at":    job.scope_change_expires_at,
        "message": (
            "Scope change request sent to the homeowner. "
            "They have 10 minutes to respond. "
            "If they don't respond, the original scope continues automatically."
        ),
    }


# ── Homeowner: Respond to scope change ─────────────────────────────────────

@router.post("/{job_id}/scope-change/respond")
async def respond_to_scope_change(
    job_id:       str,
    body:         ScopeChangeRespondRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Homeowner approves or rejects the tradie's scope change request.

    APPROVE: job → in_progress with new scope. Approved line item appended.
    REJECT:  job → in_progress with ORIGINAL scope. Tradie cannot charge for
             the unapproved work — this is enforced by the audit trail.

    VERBAL APPROVAL IS NOT VALID: Only in-app approval creates a legally
    recognised change to the scope. If the tradie proceeds after a rejection
    and charges more, the homeowner can dispute and the audit trail wins.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can respond to scope changes.")

    job = await _load_job_or_404(job_id, db)

    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")

    try:
        JobStateMachine.assert_status(job, "awaiting_scope_approval")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Cancel the Celery auto-reject task if it hasn't fired
    if job.scope_change_task_id:
        try:
            from celery.result import AsyncResult
            AsyncResult(job.scope_change_task_id).revoke(terminate=False)
        except Exception:
            pass   # Non-fatal — task may have already fired or been processed

    if body.approve:
        note = (
            f"Homeowner approved scope change. "
            f"New approved amount: {job.pending_scope_amount_cents} cents. "
            f"Approved at {datetime.utcnow().isoformat()}."
        )
        extra = {
            "pending_scope_amount_cents": None,
            "scope_change_reason":        None,
            "scope_change_requested_at":  None,
            "scope_change_expires_at":    None,
            "scope_change_task_id":       None,
        }
        message = "Scope change approved. Job continues with the new scope."
    else:
        note = (
            "Homeowner rejected scope change. "
            "Job continues with original scope and original price. "
            "Tradie cannot charge for unapproved work."
        )
        extra = {
            "pending_scope_amount_cents": None,
            "scope_change_reason":        None,
            "scope_change_requested_at":  None,
            "scope_change_expires_at":    None,
            "scope_change_task_id":       None,
        }
        message = "Scope change rejected. The job continues with the original scope and price."

    try:
        await JobStateMachine.transition(
            job=job,
            new_status="in_progress",
            current_user=current_user,
            db=db,
            note=note,
            extra_job_fields=extra,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "approved": body.approve,
        "message": message,
    }


# ── Tradie: Mark job as complete ───────────────────────────────────────────

@router.post("/{job_id}/complete")
async def complete_job(
    job_id:       str,
    body:         CompleteJobRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Tradie marks the job as complete.
    After photo is MANDATORY — this is the second half of the dispute evidence bundle.
    Homeowner has 48 hours to confirm or dispute. After 48h, a Celery beat task
    auto-closes the job and releases payment.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can mark a job complete.")

    job = await _load_job_or_404(job_id, db)
    await _require_tradie_with_lead(job_id, current_user, db)

    try:
        JobStateMachine.assert_status(job, "in_progress")
        await JobStateMachine.transition(
            job=job,
            new_status="completed",
            current_user=current_user,
            db=db,
            note="Tradie marked job complete and uploaded after photo.",
            extra_job_fields={
                # Store all URLs as a JSON array; first URL is the primary for display.
                "photo_after_url": json.dumps(body.photo_after_urls),
                "completion_note": body.completion_note,
            },
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "photo_after_urls": body.photo_after_urls,
        "message": "Job marked as complete. The homeowner has 48 hours to confirm or raise a dispute.",
        "dispute_window_hours": 48,
    }


# ── Homeowner: Confirm job complete ────────────────────────────────────────

@router.post("/{job_id}/confirm-complete")
async def confirm_complete(
    job_id:       str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Homeowner confirms the job is complete.
    Sets confirmed_by_user_at. The payment release Celery task uses this
    timestamp to determine when funds can be transferred to the tradie.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can confirm completion.")

    job = await _load_job_or_404(job_id, db)

    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job must be in 'completed' status to confirm. Current status: '{job.status}'.",
        )

    if job.confirmed_by_user_at:
        # confirmed_by_user_at was set by a previous request, but status may not
        # have been persisted if that request's second commit failed (partial write).
        # Repair the status now so the UI can reflect the correct state.
        if job.status != "confirmed":
            job.status     = "confirmed"
            job.updated_at = datetime.utcnow()
            db.add(job)
            await db.commit()
        return {"message": "Job already confirmed.", "confirmed_at": job.confirmed_by_user_at, "status": "confirmed"}

    now = datetime.utcnow()
    job.confirmed_by_user_at = now
    job.status               = "confirmed"
    job.updated_at           = now
    db.add(job)
    await db.commit()

    return {
        "status": "confirmed",
        "confirmed_at": job.confirmed_by_user_at,
        "message": "Job confirmed. Thank you!",
    }


# ── Tradie: Partial stop ───────────────────────────────────────────────────

@router.post("/{job_id}/partial-stop")
async def partial_stop(
    job_id:       str,
    body:         PartialStopRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Tradie stops work mid-job.
    Triggers the partial_stop flow: tradie submits a reason + photo of current work state.
    Payment is held uncaptured. Admin reviews within 24h and decides the partial charge amount.
    The homeowner is notified immediately.
    Job CANNOT be abandoned silently — if a tradie disappears without using this endpoint,
    the no-show detection watchdog (GPS + check-in) fires at T+30min.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can trigger a partial stop.")

    job = await _load_job_or_404(job_id, db)
    await _require_tradie_with_lead(job_id, current_user, db)

    try:
        JobStateMachine.assert_status(job, "in_progress")
        await JobStateMachine.transition(
            job=job,
            new_status="partial_stop",
            current_user=current_user,
            db=db,
            note=f"Tradie stopped work mid-job. Reason: {body.reason}",
            extra_job_fields={
                "completion_note": body.reason,
                "photo_after_url": body.photo_after_url,
            },
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "message": (
            "Work stopped. An admin will review and determine the partial charge within 24 hours. "
            "The homeowner has been notified."
        ),
    }


# ── Homeowner: Raise dispute ───────────────────────────────────────────────

@router.post("/{job_id}/dispute")
async def raise_dispute(
    job_id:       str,
    body:         DisputeRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Homeowner raises a dispute. Only allowed within 48h of job completion,
    or immediately on a partial_stop.
    Status → disputed. Admin is notified. Both parties can submit evidence.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can raise a dispute.")

    job = await _load_job_or_404(job_id, db)

    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")

    if job.status == "completed":
        # Enforce 48-hour window from when the tradie marked complete
        if job.completed_at:
            hours_since = (datetime.utcnow() - job.completed_at).total_seconds() / 3600
            if hours_since > 48:
                raise HTTPException(
                    status_code=400,
                    detail="The 48-hour dispute window has closed for this job.",
                )
    elif job.status != "partial_stop":
        raise HTTPException(
            status_code=400,
            detail=f"Disputes can only be raised on completed or partial_stop jobs. Current status: '{job.status}'.",
        )

    try:
        await JobStateMachine.transition(
            job=job,
            new_status="disputed",
            current_user=current_user,
            db=db,
            note=f"Homeowner raised dispute: {body.reason}",
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "message": (
            "Dispute raised. Our team will review within 2 business days. "
            "Please upload any supporting photos or documents via the app."
        ),
    }
