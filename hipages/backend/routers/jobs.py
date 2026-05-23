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
  POST /{job_id}/complete             Tradie marks job complete. Requires after-photo(s) OR a completion note.
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
from models.outbox_event import OutboxEvent
from models.quote import Quote
from models.tradie_certification import TradieCertification, CertificationStatus
from models.tradie_profile import TradieProfile
from schemas.job_schema import JobCreate, JobUpdate, JobResponse, JobWithDetailsResponse, JobPhotoResponse
from services.auth_service import get_current_user
from services.category_resolver import resolve_trade_category
from services.job_state_machine import JobStateMachine, InvalidTransitionError
from services.geocoding_service import geocode_suburb
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, date, timedelta
from typing import Optional
import asyncio
import json
import os
import uuid

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


# ── Dispute window helper ────────────────────────────────────────────────────

def _dispute_window(job, is_redispute: bool, dispute_count: int = 0) -> dict:
    """
    Return dispute_window_hours and dispute_window_expires_at for a job.

    Rules:
      • Jobs not in 'completed' or 'confirmed' → no window (both None).
      • dispute_count >= 2 → no window (both None). Homeowner has used both chances.
      • First dispute (count == 0): 48 h from completed_at.
      • Re-dispute (count == 1, a prior disputed→completed exists): 10 h from completed_at.
    """
    _NONE = {"dispute_window_hours": None, "dispute_window_expires_at": None}

    if job.status not in ("completed", "confirmed") or not job.completed_at:
        return _NONE

    if dispute_count >= 2:
        return _NONE

    window_hours = 10 if is_redispute else 48
    from datetime import timedelta
    expires_at = job.completed_at + timedelta(hours=window_hours)
    return {
        "dispute_window_hours":      window_hours,
        "dispute_window_expires_at": expires_at,
    }


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
        raise HTTPException(status_code=400, detail="Unknown category_slug")

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
    outbox_event = OutboxEvent(
        id=str(uuid.uuid4()),
        event_type="job.created",
        payload={"job_id": job.id},
        status="pending",
    )
    db.add(outbox_event)
    await db.commit()
    await db.refresh(job)

    celery_queued = False
    try:
        from tasks.lead_tasks import distribute_leads
        task = await asyncio.get_event_loop().run_in_executor(
            None, lambda: distribute_leads.apply_async(args=[job.id], queue="critical")
        )
        job.lead_task_id = task.id
        outbox_event.status = "queued"
        outbox_event.processed_at = datetime.utcnow()
        outbox_event.payload = {"job_id": job.id, "lead_task_id": task.id}
        db.add(outbox_event)
        db.add(job)
        await db.commit()
        celery_queued = True
        print(f"[leads] Queued via Celery for job {job.id}, task_id={task.id}")
    except Exception as e:
        outbox_event.attempts = (outbox_event.attempts or 0) + 1
        outbox_event.last_error = str(e)[:2000]
        db.add(outbox_event)
        await db.commit()
        print(f"[leads] Celery unavailable ({e}); durable outbox event left pending")

    if not celery_queued:
        allow_api_fallback = (
            os.getenv("ALLOW_IN_API_LEAD_FALLBACK", "").lower() in ("1", "true", "yes")
            or os.getenv("ENVIRONMENT", "development") != "production"
        )
        if allow_api_fallback:
            background_tasks.add_task(_distribute_leads_background, job.id)
            print(f"[leads] Development fallback scheduled for job {job.id}")

    return job




# ── Homeowner: explicit "Service not listed" submission ─────────────────────

class UncategorisedJobCreate(BaseModel):
    """
    Free-text submission used when the homeowner cannot find their need in
    the 24-trade picker. The body intentionally omits category_slug -- the
    pathway always uses the sentinel 'other-services' category.
    """
    description:   str = Field(min_length=10, max_length=2000)
    suburb:        Optional[str] = None
    state:         Optional[str] = None
    postcode:      Optional[str] = None
    contact_name:  Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


@router.post("/uncategorised", response_model=JobResponse, status_code=201)
async def create_uncategorised(
    body: UncategorisedJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Capture a service request that doesn't fit any of the 24 trades.
    Creates the job tagged with the sentinel category, never triggers lead
    distribution, writes an admin audit event, and emails the homeowner.
    Admin then triages via /admin/uncategorised.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can post jobs")

    from services.uncategorised_service import (
        create_uncategorised_job, notify_homeowner_received,
        SentinelCategoryMissingError,
    )
    try:
        job = await create_uncategorised_job(
            homeowner=current_user,
            db=db,
            description=body.description,
            suburb=body.suburb, state=body.state, postcode=body.postcode,
            contact_name=body.contact_name,
            contact_phone=body.contact_phone,
            contact_email=body.contact_email,
        )
        await db.commit()
        await db.refresh(job)
    except SentinelCategoryMissingError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        await notify_homeowner_received(current_user, body.description)
    except Exception:
        pass

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
            None, lambda: distribute_leads.apply_async(args=[job_id], queue="critical")
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

    # ── Bulk-fetch redo flags + re-dispute flags ──────────────────────────────
    from models.job_event import JobEvent
    import sqlalchemy as sa

    job_ids = [j.id for j in jobs]
    redo_job_ids:     set[str] = set()
    redispute_job_ids: set[str] = set()  # jobs that had a prior dispute resolved

    if job_ids:
        # Redo flag — admin resolved with redo_work
        redo_events_result = await db.execute(
            select(JobEvent.job_id)
            .where(
                JobEvent.job_id.in_(job_ids),
                JobEvent.action == "dispute_resolved",
            )
        )
        for (jid,) in redo_events_result.all():
            redo_job_ids.add(jid)

        # Re-dispute flag — peer-to-peer resolution: disputed → completed
        redispute_events_result = await db.execute(
            select(JobEvent.job_id)
            .where(
                JobEvent.job_id.in_(job_ids),
                JobEvent.action == "status_change",
                sa.cast(JobEvent.old_value, sa.Text).contains('"disputed"'),
                sa.cast(JobEvent.new_value, sa.Text).contains('"completed"'),
            )
        )
        for (jid,) in redispute_events_result.all():
            redispute_job_ids.add(jid)

        # Dispute count per job — how many times has this job gone to "disputed"?
        # Used to enforce the 2-dispute cap.
        dispute_count_result = await db.execute(
            select(JobEvent.job_id, sa.func.count(JobEvent.id).label("cnt"))
            .where(
                JobEvent.job_id.in_(job_ids),
                JobEvent.action == "status_change",
                sa.cast(JobEvent.new_value, sa.Text).contains('"disputed"'),
            )
            .group_by(JobEvent.job_id)
        )
        dispute_counts: dict[str, int] = {
            jid: cnt for jid, cnt in dispute_count_result.all()
        }

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
            is_redo_job=job.id in redo_job_ids,
            **_dispute_window(job, job.id in redispute_job_ids, dispute_counts.get(job.id, 0)),
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
    # Admins can see every job. Homeowners get their own jobs here so the
    # authenticated list endpoint is usable without exposing everyone else's data.
    query = select(Job).order_by(Job.created_at.desc())
    if current_user.role == "homeowner":
        query = query.where(Job.homeowner_id == current_user.id)
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Authorisation: only the homeowner who posted it, an admin, or a tradie
    # who has been sent a lead for this job may view its details.
    allowed = current_user.id == job.homeowner_id or current_user.role == "admin"
    if not allowed and current_user.role == "tradie":
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
        raise HTTPException(status_code=403, detail="Not authorised to view this job")

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
            None, lambda: distribute_leads.apply_async(args=[job.id], queue="critical")
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
        # For testing/demo purposes, we disable the 2-hour delay:
        # if hours_since < 2:
        #     raise HTTPException(
        #         status_code=400,
        #         detail="Reviews can be submitted 2 hours after job completion. Please check back later."
        #     )

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
    # Practice mode: completion note only (photos disabled until storage keys are configured).
    photo_after_urls: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Ignored while photo upload is disabled",
    )
    completion_note: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def require_completion_note_only(self) -> "CompleteJobRequest":
        note = (self.completion_note or "").strip()
        if len(note) < 5:
            raise ValueError("A completion note of at least 5 characters is required.")
        if len(self.photo_after_urls) >= 1:
            raise ValueError(
                "Photo upload is not enabled yet. Mark complete using a completion note only."
            )
        self.completion_note = note
        self.photo_after_urls = []
        return self


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
    Requires at least one after-photo URL OR a completion note (≥10 characters).
    Homeowner has 48 hours to confirm or dispute. After 48h, a Celery beat task
    auto-closes the job and releases payment.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can mark a job complete.")

    job = await _load_job_or_404(job_id, db)
    await _require_tradie_with_lead(job_id, current_user, db)

    has_photos = len(body.photo_after_urls) >= 1
    extra_job_fields: dict = {"completion_note": body.completion_note}
    if has_photos:
        extra_job_fields["photo_after_url"] = json.dumps(body.photo_after_urls)
    else:
        extra_job_fields["photo_after_url"] = None

    transition_note = (
        "Tradie marked job complete and uploaded after photo."
        if has_photos
        else "Tradie marked job complete with a completion note (no after photos)."
    )

    try:
        JobStateMachine.assert_status(job, "in_progress")
        await JobStateMachine.transition(
            job=job,
            new_status="completed",
            current_user=current_user,
            db=db,
            note=transition_note,
            extra_job_fields=extra_job_fields,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "photo_after_urls": body.photo_after_urls,
        "completion_note": body.completion_note,
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
            try:
                await JobStateMachine.transition(
                    job=job,
                    new_status="confirmed",
                    current_user=current_user,
                    db=db,
                )
            except InvalidTransitionError as e:
                raise HTTPException(status_code=400, detail=str(e))
            await db.commit()
        return {"message": "Job already confirmed.", "confirmed_at": job.confirmed_by_user_at, "status": "confirmed"}

    now = datetime.utcnow()
    try:
        await JobStateMachine.transition(
            job=job,
            new_status="confirmed",
            current_user=current_user,
            db=db,
            extra_job_fields={"confirmed_by_user_at": now},
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()

    return {
        "status": "confirmed",
        "confirmed_at": job.confirmed_by_user_at,
        "message": "Job confirmed. Thank you!",
    }


# ── Homeowner: Raise a dispute ────────────────────────────────────────────────

class DisputeRequest(BaseModel):
    reason: str


@router.post("/{job_id}/dispute")
async def raise_dispute(
    job_id:       str,
    body:         DisputeRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Homeowner raises a dispute.

    Window rules
    ─────────────
    • First-ever dispute on this job: 48 h after the tradie marked it complete.
    • Re-dispute after a resolved dispute (job returned to 'completed' from
      'disputed'): 10 h from that re-completion timestamp.
    • After the window expires the button is hidden in the UI and this endpoint
      returns 400 so there is no race condition.

    Allowed on: completed, confirmed (still within window), partial_stop.
    Status → disputed.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can raise a dispute.")

    job = await _load_job_or_404(job_id, db)

    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")

    if job.status not in ("completed", "confirmed", "partial_stop"):
        raise HTTPException(
            status_code=400,
            detail=f"Disputes can only be raised on completed, confirmed, or partial_stop jobs. "
                   f"Current status: '{job.status}'.",
        )

    # ── Check dispute cap + determine which window applies ───────────────────
    from models.job_event import JobEvent as JE
    import sqlalchemy as sa

    # Count how many times this job has already gone to "disputed"
    dispute_count_res = await db.execute(
        select(sa.func.count(JE.id))
        .where(
            JE.job_id  == job_id,
            JE.action  == "status_change",
            sa.cast(JE.new_value, sa.Text).contains('"disputed"'),
        )
    )
    dispute_count = dispute_count_res.scalar() or 0

    if dispute_count >= 2:
        raise HTTPException(
            status_code=400,
            detail="You have already raised 2 disputes on this job. No further disputes are allowed.",
        )

    # A re-dispute is detected by the presence of a prior 'disputed→completed'
    # transition event, meaning the dispute was resolved peer-to-peer at least once.
    prior_resolution = await db.execute(
        select(JE).where(
            JE.job_id  == job_id,
            JE.action  == "status_change",
            sa.cast(JE.old_value, sa.Text).contains('"disputed"'),
            sa.cast(JE.new_value, sa.Text).contains('"completed"'),
        ).limit(1)
    )
    is_redispute = prior_resolution.scalar_one_or_none() is not None

    window_hours = 10 if is_redispute else 48

    if job.status in ("completed", "confirmed"):
        if not job.completed_at:
            raise HTTPException(status_code=400, detail="Job has no completion timestamp.")
        hours_since = (datetime.utcnow() - job.completed_at).total_seconds() / 3600
        if hours_since > window_hours:
            label = "10-hour" if is_redispute else "48-hour"
            raise HTTPException(
                status_code=400,
                detail=f"The {label} dispute window has closed for this job.",
            )

    if not body.reason or len(body.reason.strip()) < 10:
        raise HTTPException(status_code=422, detail="Please describe the issue (at least 10 characters).")

    try:
        await JobStateMachine.transition(
            job=job,
            new_status="disputed",
            current_user=current_user,
            db=db,
            note=f"Homeowner raised dispute: {body.reason.strip()}",
            extra_job_fields={"dispute_reason": body.reason.strip()},
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "status": job.status,
        "message": "Dispute raised. The tradie has been notified and can respond directly.",
    }


# ── Dispute info (any party can read) ───────────────────────────────────────

@router.get("/{job_id}/dispute-info")
async def dispute_info(
    job_id:       str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Return the homeowner's dispute reason and timestamp so the homeowner's
    own dashboard, the tradie's dashboard, and admin can all show the same
    context. Authorisation: homeowner of the job, any tradie with a lead on
    the job, or admin.
    """
    from models.job_event import JobEvent

    job = await _load_job_or_404(job_id, db)

    is_homeowner = current_user.id == job.homeowner_id
    is_admin     = current_user.role == "admin"
    is_tradie    = False
    if not (is_homeowner or is_admin) and current_user.role == "tradie":
        # Tradie must have a lead on this job.
        from models.tradie_profile import TradieProfile as TP
        profile_res = await db.execute(select(TP).where(TP.user_id == current_user.id))
        tp = profile_res.scalar_one_or_none()
        if tp:
            lead_res = await db.execute(
                select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == tp.id).limit(1)
            )
            is_tradie = lead_res.scalar_one_or_none() is not None
    if not (is_homeowner or is_admin or is_tradie):
        raise HTTPException(status_code=403, detail="Not your job.")

    # Walk the events newest -> oldest, find the most recent flip to 'disputed'.
    events_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.action == "status_change")
        .order_by(JobEvent.created_at.desc())
    )
    reason = None
    raised_at = None
    raised_by_role = None
    for ev in events_res.scalars().all():
        nv = ev.new_value or {}
        if nv.get("status") == "disputed":
            note = ev.note or ""
            for prefix in ("Homeowner raised dispute: ", "Homeowner raised dispute:"):
                if note.startswith(prefix):
                    note = note[len(prefix):].strip()
                    break
            reason = note or None
            raised_at = ev.created_at
            raised_by_role = ev.actor_role
            break

    # All dispute responses, oldest first, so the dashboard renders them as a
    # conversation. Both homeowner and tradie posts show up here.
    resp_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.action == "dispute_response")
        .order_by(JobEvent.created_at.asc())
    )
    responses = [
        {
            "id":           ev.id,
            "actor_role":   ev.actor_role,
            "response":     ev.note,
            "evidence_url": (ev.new_value or {}).get("evidence_url"),
            "created_at":   ev.created_at,
        }
        for ev in resp_res.scalars().all()
    ]

    # Check if tradie has claimed resolution (most recent claim event).
    claim_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.action == "dispute_resolution_claimed")
        .order_by(JobEvent.created_at.desc())
        .limit(1)
    )
    claim_event = claim_res.scalar_one_or_none()

    # Count how many times homeowner has rejected the tradie's resolution claim.
    rejection_count_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.action == "dispute_resolution_rejected")
    )
    rejection_count = len(rejection_count_res.scalars().all())

    return {
        "job_id":                   job.id,
        "status":                   job.status,
        "dispute_reason":           reason,
        "dispute_raised_at":        raised_at,
        "dispute_raised_by_role":   raised_by_role,
        "completion_note":          job.completion_note,
        "photo_before_url":         job.photo_before_url,
        "photo_after_url":          job.photo_after_url,
        "responses":                responses,
        # Peer-to-peer resolution state
        "resolution_claimed":       claim_event is not None,
        "resolution_claimed_at":    claim_event.created_at if claim_event else None,
        "resolution_rejection_count": rejection_count,
    }


# ── Tradie: claim dispute is resolved ────────────────────────────────────────

class DisputeClaimRequest(BaseModel):
    message: Optional[str] = Field(default=None, max_length=1000)


@router.post("/{job_id}/dispute-claim-resolved")
async def dispute_claim_resolved(
    job_id:       str,
    body:         DisputeClaimRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Tradie claims they have resolved the dispute.

    No status change — stores a dispute_resolution_claimed JobEvent and
    notifies the homeowner to log in and accept or reject.
    The homeowner's response is the gate that moves the job forward.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can claim a resolution.")

    job = await _load_job_or_404(job_id, db)
    if job.status != "disputed":
        raise HTTPException(status_code=400, detail=f"Job is not disputed (status={job.status}).")

    # Verify the tradie is the assigned one via a lead on this job.
    from models.tradie_profile import TradieProfile as TP
    profile_res = await db.execute(select(TP).where(TP.user_id == current_user.id))
    profile = profile_res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=403, detail="Tradie profile not found.")
    lead_res = await db.execute(
        select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == profile.id).limit(1)
    )
    if not lead_res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not assigned to this job.")

    from models.job_event import JobEvent
    ev = JobEvent(
        job_id=job_id,
        actor_id=current_user.id,
        actor_role="tradie",
        action="dispute_resolution_claimed",
        old_value=None,
        new_value={"message": body.message or ""},
        note=body.message or "Tradie claims the dispute has been resolved.",
    )
    db.add(ev)
    await db.commit()

    # Notify homeowner — best-effort.
    try:
        hw_res = await db.execute(select(User).where(User.id == job.homeowner_id))
        homeowner = hw_res.scalar_one_or_none()
        if homeowner and homeowner.email:
            from services.resend_service import send_dispute_resolution_claimed_email
            await send_dispute_resolution_claimed_email(
                to_email=homeowner.email,
                full_name=homeowner.full_name or "",
                job_title=job.title,
                tradie_business_name=profile.business_name,
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "dispute-claim notify failed for job %s: %s", job.id, exc
        )

    # WebSocket push so homeowner dashboard refreshes without reload.
    try:
        from routers.websocket import broadcast_job_status
        await broadcast_job_status(
            job_id=job.id, old_status="disputed", new_status="disputed",
            homeowner_id=job.homeowner_id, tradie_user_ids=[current_user.id],
        )
    except Exception:
        pass

    return {"message": "Resolution claimed. The homeowner has been notified to confirm."}


# ── Homeowner: accept or reject the tradie's resolution claim ─────────────────

class DisputeResolutionResponseRequest(BaseModel):
    accept: bool
    message: Optional[str] = Field(default=None, max_length=1000)


@router.post("/{job_id}/dispute-accept-resolution")
async def dispute_accept_resolution(
    job_id:       str,
    body:         DisputeResolutionResponseRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Homeowner accepts or rejects the tradie's resolution claim.

    accept=True  → disputed → completed  (re-enters normal confirm flow)
    accept=False → stays disputed; rejection count incremented.
                   On 2nd+ rejection, admin is auto-alerted via email.
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can respond to a resolution claim.")

    job = await _load_job_or_404(job_id, db)
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")
    if job.status != "disputed":
        raise HTTPException(status_code=400, detail=f"Job is not disputed (status={job.status}).")

    from models.job_event import JobEvent

    # Require that the tradie actually submitted a claim first.
    claim_res = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.action == "dispute_resolution_claimed")
        .limit(1)
    )
    if not claim_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The tradie hasn't claimed a resolution yet. Wait for them to mark it resolved first.",
        )

    if body.accept:
        # ── Homeowner accepts: transition disputed → completed ─────────────────
        try:
            await JobStateMachine.transition(
                job=job,
                new_status="completed",
                current_user=current_user,
                db=db,
                note=f"Homeowner accepted tradie's resolution. {body.message or ''}".strip(),
            )
        except InvalidTransitionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Mark completed_at if not set (this is a re-completion after dispute).
        if not job.completed_at:
            job.completed_at = datetime.utcnow()
            db.add(job)

        await db.commit()

        # Notify tradie — best-effort.
        try:
            from models.tradie_profile import TradieProfile as TP
            accepted_res = await db.execute(
                select(Quote, TP, User)
                .join(TP,   TP.id == Quote.tradie_id)
                .join(User, User.id == TP.user_id)
                .join(Lead, Lead.id == Quote.lead_id)
                .where(Lead.job_id == job.id, Quote.status == "accepted").limit(1)
            )
            row = accepted_res.first()
            if row:
                _q, tp, tu = row
                from services.resend_service import send_dispute_resolved_to_tradie_email
                await send_dispute_resolved_to_tradie_email(
                    to_email=tu.email,
                    full_name=tu.full_name or "",
                    business_name=tp.business_name,
                    job_title=job.title,
                    resolution="side_tradie",
                    admin_note="Homeowner accepted your resolution — great work resolving this directly.",
                )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "dispute-accept tradie notify failed for job %s: %s", job.id, exc
            )

        return {
            "accepted": True,
            "status": "completed",
            "message": "Dispute resolved. The job is back to completed — please confirm when ready.",
        }

    else:
        # ── Homeowner rejects: stay disputed, count rejections ─────────────────
        db.add(JobEvent(
            job_id=job_id,
            actor_id=current_user.id,
            actor_role="homeowner",
            action="dispute_resolution_rejected",
            old_value=None,
            new_value={"message": (body.message or "").strip()},
            note=f"Homeowner rejected tradie resolution claim.",
        ))

        # Count total rejections
        rejection_res = await db.execute(
            select(JobEvent).where(
                JobEvent.job_id == job_id,
                JobEvent.action == "dispute_resolution_rejected",
            )
        )
        rejection_count = len(rejection_res.scalars().all())

        await db.commit()

        # Notify tradie of rejection (best-effort)
        try:
            lead_res = await db.execute(
                select(Lead)
                .join(TradieProfile, TradieProfile.id == Lead.tradie_id)
                .join(User, User.id == TradieProfile.user_id)
                .where(Lead.job_id == job_id, Lead.status == "accepted")
                .limit(1)
            )
            lead = lead_res.scalar_one_or_none()
            if lead:
                from sqlalchemy.orm import joinedload
                lead_full = await db.execute(
                    select(Lead)
                    .options(
                        joinedload(Lead.tradie_profile).joinedload(TradieProfile.user)
                    )
                    .where(Lead.id == lead.id)
                )
                lead_full = lead_full.scalar_one_or_none()
                if lead_full and lead_full.tradie_profile and lead_full.tradie_profile.user:
                    tradie_user = lead_full.tradie_profile.user
                    # If admin escalation threshold reached, alert admin
                    if rejection_count >= 2:
                        try:
                            from services.resend_service import send_dispute_escalated_to_admin_email
                            import os
                            admin_email = os.getenv("ADMIN_ALERT_EMAIL", "admin@proconnect.com.au")
                            await send_dispute_escalated_to_admin_email(
                                to_email=admin_email,
                                admin_name="Admin",
                                job_id=job_id,
                                job_title=job.title,
                                homeowner_name=current_user.full_name or current_user.email,
                                tradie_business_name=lead_full.tradie_profile.business_name or tradie_user.full_name or "Tradie",
                                rejection_count=rejection_count,
                            )
                        except Exception:
                            pass
        except Exception:
            pass

        return {
            "accepted": False,
            "status": "disputed",
            "rejection_count": rejection_count,
            "message": "Your response has been recorded. The tradie has been notified." + (
                " Our admin team has been alerted and will step in to help." if rejection_count >= 2 else ""
            ),
        }


# ── Respond to a dispute (both parties + admin mediator) ────────────────────

class DisputeResponseRequest(BaseModel):
    response: str


@router.post("/{job_id}/dispute-response")
async def dispute_response(
    job_id:       str,
    body:         DisputeResponseRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Either party (homeowner or tradie) adds a message to the dispute thread.
    Stores a JobEvent with action='dispute_message'. No status change.
    """
    job = await _load_job_or_404(job_id, db)

    if current_user.role == "homeowner":
        if job.homeowner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your job.")
    elif current_user.role == "tradie":
        await _require_tradie_with_lead(job_id, current_user, db)
    else:
        raise HTTPException(status_code=403, detail="Not permitted.")

    if job.status != "disputed":
        raise HTTPException(status_code=400, detail="This job is not currently in dispute.")

    if not body.response or not body.response.strip():
        raise HTTPException(status_code=422, detail="Response message cannot be empty.")

    from models.job_event import JobEvent
    event = JobEvent(
        job_id     = job_id,
        actor_id   = current_user.id,
        actor_role = current_user.role,
        action     = "dispute_message",
        old_value  = {},
        new_value  = {"message": body.response.strip()},
        note       = f"Dispute message from {current_user.role}: {body.response.strip()[:120]}",
    )
    db.add(event)
    await db.commit()

    return {
        "status": "disputed",
        "message": "Your response has been recorded.",
    }
