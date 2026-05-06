from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.quote import Quote
from models.lead import Lead
from models.tradie_profile import TradieProfile
from models.job import Job
from models.user import User
from schemas.quote_schema import QuoteCreate, QuoteResponse
from services.auth_service import get_current_user
from services.job_state_machine import JobStateMachine, InvalidTransitionError
import uuid

router = APIRouter(prefix="/api/v1/quotes", tags=["Quotes"])


@router.post("/", response_model=QuoteResponse, status_code=201)
async def create_quote(
    body: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can send quotes")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    result = await db.execute(
        select(Lead).where(Lead.id == body.lead_id, Lead.tradie_id == profile.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await db.execute(select(Quote).where(Quote.lead_id == body.lead_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Quote already sent for this lead")

    quote = Quote(
        id=str(uuid.uuid4()),
        lead_id=body.lead_id,
        tradie_id=profile.id,
        amount=body.amount,
        message=body.message,
        status="pending"
    )
    db.add(quote)
    lead.status = "quoted"
    db.add(lead)

    job_result = await db.execute(select(Job).where(Job.id == lead.job_id))
    job = job_result.scalar_one_or_none()
    if job and job.status == "open":
        try:
            await JobStateMachine.transition(job, "quoted", current_user, db)
        except InvalidTransitionError:
            pass

    await db.commit()
    await db.refresh(quote)
    return quote

@router.get("/my-quote/{lead_id}", response_model=QuoteResponse)
async def get_my_quote_for_lead(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Tradie fetches their own quote for a specific lead."""
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    result = await db.execute(
        select(Quote).where(
            Quote.lead_id == lead_id,
            Quote.tradie_id == profile.id,
        )
    )
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="No quote found for this lead")

    return quote


@router.get("/job/{job_id}", response_model=list[QuoteResponse])
async def get_quotes_for_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    result = await db.execute(
        select(Quote)
        .join(Lead, Lead.id == Quote.lead_id)
        .where(Lead.job_id == job_id)
        .order_by(Quote.created_at.asc())
    )
    return result.scalars().all()


@router.patch("/{quote_id}/status", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Homeowner accepts or rejects a quote.
    - accepted → job transitions to hired; all other pending quotes auto-rejected
    - rejected  → if no remaining accepted quotes, job reverts to open
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can accept/reject quotes")
    if new_status not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'accepted' or 'rejected'")

    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lead_result = await db.execute(select(Lead).where(Lead.id == quote.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    job_result = await db.execute(select(Job).where(Job.id == lead.job_id))
    job = job_result.scalar_one_or_none()
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    quote.status = new_status
    db.add(quote)

    # Fetch all lead ids for this job
    all_leads_result = await db.execute(select(Lead).where(Lead.job_id == job.id))
    all_lead_ids = [l.id for l in all_leads_result.scalars().all()]

    if new_status == "accepted":
        # Auto-reject all other pending quotes
        others_result = await db.execute(
            select(Quote).where(
                Quote.lead_id.in_(all_lead_ids),
                Quote.id != quote_id,
                Quote.status == "pending"
            )
        )
        for other in others_result.scalars().all():
            other.status = "rejected"
            db.add(other)
        try:
            await JobStateMachine.transition(job, "hired", current_user, db)
        except InvalidTransitionError:
            pass

    elif new_status == "rejected":
        # Check if any accepted quote still exists
        accepted_result = await db.execute(
            select(Quote).where(
                Quote.lead_id.in_(all_lead_ids),
                Quote.status == "accepted"
            )
        )
        if not accepted_result.scalar_one_or_none():
            # No accepted quote → reopen job so new tradies can quote
            if job.status in ("quoted", "hired"):
                try:
                    await JobStateMachine.transition(job, "open", current_user, db)
                except InvalidTransitionError:
                    pass

    await db.commit()
    await db.refresh(quote)
    return quote