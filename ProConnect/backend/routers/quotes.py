"""
backend/routers/quotes.py

All quote endpoints — tradies submit quotes, homeowners view/accept/reject them.
The get_quotes_for_job endpoint joins TradieProfile so the homeowner can
see the tradie's name, business and suburb on each quote card.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.job import Job
from models.lead import Lead
from models.quote import Quote
from models.tradie_profile import TradieProfile
from models.user import User
from schemas.quote_schema import QuoteCreate, QuoteResponse
from services.auth_service import get_current_user
from services.job_state_machine import InvalidTransitionError, JobStateMachine

router = APIRouter(prefix="/api/v1/quotes", tags=["Quotes"])


# ── Tradie: Submit a quote ───────────────────────────────────────────────

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
    job_result = await db.execute(select(Job).where(Job.id == lead.job_id))
    job = job_result.scalar_one_or_none()
    if job and job.status == "open":
        try:
            await JobStateMachine.system_transition(
                job,
                "quoted",
                db,
                note="Tradie submitted the first quote for this job.",
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(quote)

    # Notify homeowner a new quote arrived (best-effort — non-fatal)
    try:
        await _notify_homeowner_new_quote(job, current_user, profile, body.amount, db)
    except Exception:
        pass

    return _build_quote_response(quote, profile, current_user)


# ── Tradie: Get own quote for a lead ──────────────────────────────────────────────

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


# ── Homeowner: View all quotes for a job ──────────────────────────────────────────────

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
        phone = tradie_user.phone if quote.status == "accepted" else None
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


# ── Homeowner: Accept or reject a quote ───────────────────────────────────────────────

@router.patch("/{quote_id}/status", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Homeowner accepts or rejects a quote.
      accepted -> job transitions to in_progress; all other pending quotes auto-rejected
      rejected -> if no remaining accepted quotes, job reverts to open
    """
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can accept/reject quotes")
    if new_status not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'accepted' or 'rejected'")

    result = await db.execute(select(Quote).where(Quote.id == quote_id).with_for_update())
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lead_result = await db.execute(select(Lead).where(Lead.id == quote.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    job_result = await db.execute(select(Job).where(Job.id == lead.job_id).with_for_update())
    job = job_result.scalar_one_or_none()
    if not job or job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")

    # Load tradie profile before commit
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

    # ---- Snapshot ALL values needed for the response BEFORE any commit ----
    # After db.commit(), SQLAlchemy marks every ORM object as expired.
    # Accessing an expired attribute in an async session triggers a lazy load
    # which raises MissingGreenlet (surfaced to the client as HTTP 500).
    # Extract everything into plain Python scalars right now while the
    # session is still live and all objects are fully loaded.
    tradie_name     = profile.business_name or tradie_user.full_name or "Tradie"
    tradie_business = profile.business_name
    tradie_avatar   = profile.avatar_url
    tradie_suburb   = profile.suburb
    tradie_phone    = tradie_user.phone  # filtered below: only revealed on accept

    q_id         = quote.id
    q_lead_id    = quote.lead_id
    q_tradie_id  = quote.tradie_id
    q_amount     = quote.amount
    q_message    = quote.message
    q_created_at = quote.created_at
    job_id_val   = job.id
    job_status   = job.status
    # -----------------------------------------------------------------------

    quote.status = new_status
    db.add(quote)

    if new_status == "rejected":
        lead.status = "rejected"
        db.add(lead)

    # Fetch all lead ids and objects for this job
    all_leads_result = await db.execute(select(Lead).where(Lead.job_id == job_id_val))
    all_leads = all_leads_result.scalars().all()
    all_lead_ids = [ld.id for ld in all_leads]

    if new_status == "accepted":
        accepted_result = await db.execute(
            select(Quote).where(
                Quote.lead_id.in_(all_lead_ids),
                Quote.id != quote_id,
                Quote.status == "accepted",
            )
        )
        if accepted_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="This job already has an accepted quote")

        # Auto-reject all other pending quotes for this job
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

        # Update all lead statuses for the job
        for ld in all_leads:
            if ld.id == lead.id:
                ld.status = "accepted"
            else:
                ld.status = "rejected"
            db.add(ld)

        # Move job through the state machine while the job row is locked.
        TERMINAL = {"in_progress", "completed", "closed", "cancelled"}
        if job_status not in TERMINAL:
            target_status = "hired" if job_status == "quoted" else "in_progress"
            try:
                if job_status == "open":
                    await JobStateMachine.system_transition(
                        job,
                        "quoted",
                        db,
                        note="Quote accepted before job was marked quoted.",
                    )
                    await JobStateMachine.transition(job, "hired", current_user, db)
                elif target_status == "hired":
                    await JobStateMachine.transition(job, "hired", current_user, db)
                if job.status == "hired":
                    await JobStateMachine.system_transition(
                        job,
                        "in_progress",
                        db,
                        note="Job moved in progress after homeowner accepted quote.",
                    )
            except InvalidTransitionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    elif new_status == "rejected":
        # Reopen job only if no accepted quote remains for this job
        accepted_result = await db.execute(
            select(Quote).where(
                Quote.lead_id.in_(all_lead_ids),
                Quote.status == "accepted",
            )
        )
        if not accepted_result.scalar_one_or_none():
            if job_status in ("quoted", "hired"):
                try:
                    await JobStateMachine.transition(job, "open", current_user, db)
                except Exception as e:
                    if not isinstance(e, InvalidTransitionError):
                        print(f"[quotes] State machine error on reopen (non-fatal): {e}")

    await db.commit()
    # All ORM objects are expired past this point -- use only local vars above

    return QuoteResponse(
        id=q_id,
        lead_id=q_lead_id,
        tradie_id=q_tradie_id,
        amount=q_amount,
        message=q_message,
        status=new_status,
        created_at=q_created_at,
        tradie_name=tradie_name,
        tradie_business=tradie_business,
        tradie_avatar_url=tradie_avatar,
        tradie_phone=tradie_phone if new_status == "accepted" else None,
        tradie_suburb=tradie_suburb,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────────────────

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

        from services.resend_service import _btn, _first

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

        from services.resend_service import _base_html, _send_raw_email
        html_content = _base_html(body, "#2E7D5A")
        text_content = f"G'day {name}, {tradie_display} has submitted a quote of ${amount:,.2f} for your job \"{job.title}\"."
        await _send_raw_email(homeowner.email, "New quote received!", html_content, text_content)
    except Exception as e:
        print(f"[quotes] Homeowner notification failed (non-fatal): {e}")
