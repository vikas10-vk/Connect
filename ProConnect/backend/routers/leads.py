from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.session import get_db
from models.lead import Lead
from models.job import Job
from models.tradie_profile import TradieProfile
from models.user import User
from schemas.lead_schema import LeadResponse
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/leads", tags=["Leads"])

# Urgency values that trigger the Urgent badge
URGENT_VALUES = {"asap", "emergency"}

# Budget threshold (AUD) for High Value badge
HIGH_VALUE_THRESHOLD = 1000.0


@router.get("/my-leads", response_model=list[LeadResponse])
async def my_leads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all leads for the authenticated tradie.
    Each lead includes full job details and badge flags.
    Fixes the N+1 query — loads all leads + jobs in 2 queries total.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can view leads")

    # Get tradie profile
    profile_result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    # ── Single query: leads + job in one join (fixes N+1) ─────────
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.job))
        .where(Lead.tradie_id == profile.id)
        .order_by(Lead.sent_at.desc())
    )
    leads = result.scalars().all()

    # ── Build response with badge logic ───────────────────────────
    response = []
    for lead in leads:
        job = lead.job

        # Compute badges
        is_urgent = (
            job.urgency in URGENT_VALUES
            if job and job.urgency else False
        )
        is_high_value = (
            job.budget_max >= HIGH_VALUE_THRESHOLD
            if job and job.budget_max else False
        )

        response.append(LeadResponse(
            id=lead.id,
            job_id=lead.job_id,
            tradie_id=lead.tradie_id,
            credits_charged=lead.credits_charged,
            status=lead.status,
            sent_at=lead.sent_at,

            # Job details
            job_title=job.title             if job else None,
            job_suburb=job.suburb           if job else None,
            job_state=job.state             if job else None,
            job_description=job.description if job else None,
            job_budget_min=job.budget_min   if job else None,
            job_budget_max=job.budget_max   if job else None,
            job_urgency=job.urgency         if job else None,
            job_status=job.status           if job else None,

            # Wizard fields
            job_type=job.job_type           if job else None,
            service_type=job.service_type   if job else None,
            job_stage=job.job_stage         if job else None,

            # Badges
            is_urgent=is_urgent,
            is_high_value=is_high_value,
        ))

    return response