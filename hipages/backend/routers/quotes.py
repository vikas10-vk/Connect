"""
backend/routers/quotes.py

All quote endpoints — tradies submit quotes, homeowners view/accept/reject them.
The get_quotes_for_job endpoint now joins TradieProfile so the homeowner can
see the tradie's name, business and suburb on each quote card.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
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


# ── Tradie: Submit a quote ─────────────────────────────────────────────────────

@router.post("/", response_model=QuoteResponse, status_code=201)
async def create_quote(
    body: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Tradie submits a quote on a lead they received."""
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can send quotes")

    # Verify tradie has a profile
    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    # Verify the lead belongs to this tradie
    result = await db.execute(
        select(Lead).where(Lead.id == body.lead_id, Lead.tradie_id == profile.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found or does not belong to you")

    # One quote per lead only
    result = await db.execute(select(Quote).where(Quote.lead_id == body.lead_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already sent a quote for this lead")

    quote = Quote(
        id=str(uuid.uuid4()),
        lead_id=body.lead_id,
        tradie_id=profile.id,
        amount=body.amount,
        message=body.message,
        status="pending",
    )
    db.add(quote)

    # Mark lead as quoted
    lead.status = "quoted"
    db.add(lead)

    # Transition job → quoted if it's still open.
    # Lead distribution should already have done this, but guard for old data /
    # race conditions by doing it directly (no state-machine actor check needed here).
    job_result = await db.execute(select(Job).where(Job.id == lead.job_id))
    job = job_result.scalar_one_or_none()
    if job and job.status == "open":
        from datetime import datetime as _dt
        job.status = "quoted"
        job.updated_at = _dt.utcnow()
        db.add(job)

    await db.commit()
    await db.refresh(quote)

    # Notify homeowner a new quote arrived (best-effort — non-fatal)
    try:
        await _notify_homeowner_new_quote(job, current_user, profile, body.amount, db)
    except Exception:
        pass

    return _build_quote_response(quote, profile, current_user)


# ── Tradie: Get own quote for a lead ──────────────────────────────────────────

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

    return _build_quote_response(quote, profile, current_user)


# ── Homeowner: View all quotes for a job ──────────────────────────────────────

@router.get("/job/{job_id}", response_model=list[QuoteResponse])
async def get_quotes_for_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Homeowner fetches all quotes for one of their jobs.
    Returns full tradie info (name, suburb, avatar) so the homeowner can
    compare tradies without needing a separate profile lookup.
    """
    # Verify ownership
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    # Load all quotes for this job together with the tradie profile & user
    result = await db.execute(
        select(Quote, TradieProfile, User)
        .join(Lead, Lead.id == Quote.lead_id)
        .join(TradieProfile, TradieProfile.id == Quote.tradie_id)
        .join(User, User.id == TradieProfile.user_id)
        .where(Lead.job_id == job_id)
        .order_by(Quote.created_at.asc())
    )
    rows = result.all()

    responses = []
    for quote, profile, tradie_user in rows:
        display_name = profile.business_name or tradie_user.full_name or "Tradie"
        # Only reveal phone number after quote is accepted
        phone = profile.phone if quote.status == "accepted" else None
        responses.append(QuoteResponse(
            id=quote.id,
            lead_id=quote.lead_id,
            tradie_id=quote.tradie_id,
            amount=quote.amount,
            message=quote.message,
            status=quote.status,
            created_at=quote.created_at,
            tradie_name=display_name,
            tradie_business=profile.business_name,
            tradie_avatar_url=profile.avatar_url,
            tradie_phone=phone,
            tradie_suburb=profile.suburb,
        ))

    return responses


# ── Homeowner: Accept or reject a quote ───────────────────────────────────────

@router.patch("/{quote_id}/status", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Homeowner accepts or rejects a quote.
      accepted → job transitions to in_progress; all other pending quotes auto-rejected
      rejected → if no remaining accepted quotes, job reverts to open
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

    # ── Load tradie profile BEFORE commit so we always have it for the response ─
    # (After db.commit() SQLAlchemy expires ORM objects; a post-commit JOIN can
    #  silently return nothing and previously triggered a spurious 500 error.)
    prof_result = await db.execute(
        select(TradieProfile, User)
        .join(User, User.id == TradieProfile.user_id)
        .where(TradieProfile.id == quote.tradie_id)
    )
    prof_row = prof_result.first()
    if not prof_row:
        print(f"[quotes] WARNING: tradie profile not found for quote {quote_id}, tradie_id={quote.tradie_id}")
        raise HTTPException(status_code=404, detail="Tradie profile not found for this quote")
    profile, tradie_user = prof_row

    # Snapshot values we need for the response into plain local variables so
    # they survive db.commit() (which would otherwise expire the ORM objects).
    tradie_name     = profile.business_name or tradie_user.full_name or "Tradie"
    tradie_business = profile.business_name
    tradie_avatar   = profile.avatar_url
    tradie_suburb   = profile.suburb
    tradie_phone    = profile.phone  # only exposed when accepted (filtered below)

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
                Quote.status == "pending",
            )
        )
        for other in others_result.scalars().all():
            other.status = "rejected"
            db.add(other)

        # Move job to in_progress via explicit SQL so it is guaranteed to
        # persist regardless of SQLAlchemy ORM session-tracking edge cases.
        TERMINAL = {"in_progress", "completed", "closed", "cancelled"}
        if job.status not in TERMINAL:
            await db.execute(
                text("UPDATE jobs SET status='in_progress', updated_at=NOW() WHERE id=:jid"),
                {"jid": job.id},
            )

    elif new_status == "rejected":
        # Reopen job if no accepted quote remains
        accepted_result = await db.execute(
            select(Quote).where(
                Quote.lead_id.in_(all_lead_ids),
                Quote.status == "accepted",
            )
        )
        if not accepted_result.scalar_one_or_none():
            if job.status in ("quoted", "hired"):
                try:
                    await JobStateMachine.transition(job, "open", current_user, db)
                except Exception as e:
                    if not isinstance(e, InvalidTransitionError):
                        print(f"[quotes] State machine error on reopen (non-fatal): {e}")
                # Explicit UPDATE as source of truth
                await db.execute(
                    text("UPDATE jobs SET status='open', updated_at=NOW() WHERE id=:jid"),
                    {"jid": job.id},
                )

    await db.commit()

    # Snapshot quote fields before the session expiry invalidates them
    q_id         = quote.id
    q_lead_id    = quote.lead_id
    q_tradie_id  = quote.tradie_id
    q_amount     = quote.amount
    q_message    = quote.message
    q_status     = quote.status
    q_created_at = quote.created_at

    return QuoteResponse(
        id=q_id,
        lead_id=q_lead_id,
        tradie_id=q_tradie_id,
        amount=q_amount,
        message=q_message,
        status=q_status,
        created_at=q_created_at,
        tradie_name=tradie_name,
        tradie_business=tradie_business,
        tradie_avatar_url=tradie_avatar,
        tradie_phone=tradie_phone if new_status == "accepted" else None,
        tradie_suburb=tradie_suburb,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_quote_response(quote: Quote, profile: TradieProfile, tradie_user: User) -> QuoteResponse:
    """Build a QuoteResponse including tradie details."""
    return QuoteResponse(
        id=quote.id,
        lead_id=quote.lead_id,
        tradie_id=quote.tradie_id,
        amount=quote.amount,
        message=quote.message,
        status=quote.status,
        created_at=quote.created_at,
        tradie_name=profile.business_name or tradie_user.full_name or "Tradie",
        tradie_business=profile.business_name,
        tradie_avatar_url=profile.avatar_url,
        tradie_phone=None,  # Not revealed until accepted
        tradie_suburb=profile.suburb,
    )


async def _notify_homeowner_new_quote(job, tradie_user: User, profile: TradieProfile, amount: float, db) -> None:
    """Send email to homeowner when a new quote arrives on their job."""
    try:
        from sqlalchemy import select as _select
        from services.resend_service import _send_raw_email, _base_html, _btn, _first, APP_NAME

        homeowner_res = await db.execute(_select(User).where(User.id == job.homeowner_id))
        homeowner = homeowner_res.scalar_one_or_none()
        if not homeowner:
            return

        tradie_display = profile.business_name or tradie_user.full_name or "A tradie"
        name = _first(homeowner.full_name or "")
        body = f"""
          <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:26px;
                     font-weight:500;color:#1A1A1A;">New quote received!</h1>
          <p style="margin:0 0 20px;font-size:14.5px;line-height:1.7;color:#4A4A48;">
            G'day {name}, <strong>{tradie_display}</strong> has submitted a quote
            for your job <strong>"{job.title}"</strong>.
          </p>
          <div style="background:#F0FDF4;border:1px solid #2E7D5A33;border-radius:12px;
                      padding:16px 20px;margin:20px 0;">
            <p style="margin:0;font-size:22px;font-weight:800;color:#1A1A1A;">
              ${amount:,.2f}
            </p>
            <p style="margin:4px 0 0;font-size:13px;color:#4A4A48;">Quoted price</p>
          </div>
          <p style="margin:0 0 20px;font-size:13.5px;line-height:1.7;color:#4A4A48;">
            Log in to your dashboard to review the quote, compare tradies and accept.
          </p>
          {_btn("View Quote", "http://localhost:3000/dashboard", "#2E7D5A")}"""
        text = (
            f"G'day {name},\n\n"
            f"{tradie_display} has quoted ${amount:,.2f} for '{job.title}'.\n\n"
            f"View and accept quotes: http://localhost:3000/dashboard\n\n"
            f"— The {APP_NAME} team"
        )
        await _send_raw_email(
            homeowner.email,
            f"New quote received for {job.title}",
            _base_html(body, "#2E7D5A"),
            text,
        )
    except Exception as e:
        print(f"[quotes] Homeowner notification failed (non-fatal): {e}")
