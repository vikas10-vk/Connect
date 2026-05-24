"""
services/earnings_service.py

Tradie earnings ledger.

Earnings are booked ONLY when a job is finally `closed` — meaning either:
  * The 48-hour homeowner dispute window has passed without dispute
    (auto_close_completed_jobs beat task moved status -> closed), OR
  * An admin closed the job (e.g. after resolving a dispute).

We deliberately do NOT book on `confirmed` because the homeowner can still
escalate confirmed -> disputed within the 48-hour window. Booking on
`confirmed` would mean a tradie sees the earning, then it disappears
again if the homeowner spots a problem in hour 30 and disputes.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.earnings_record import EarningsRecord

GST_THRESHOLD   = 75000.0
GST_RATE        = 0.10
TAX_BUFFER_RATE = 0.25
PLATFORM_FEE    = 0.03


async def get_monthly_summary(tradie_id: str, db: AsyncSession) -> dict:
    now   = datetime.utcnow()
    month = now.month
    year  = now.year

    # This month gross
    month_result = await db.execute(
        select(func.sum(EarningsRecord.gross_amount))
        .where(
            EarningsRecord.tradie_id == tradie_id,
            EarningsRecord.month     == month,
            EarningsRecord.year      == year,
        )
    )
    month_gross = month_result.scalar() or 0.0

    # Year to date gross
    ytd_result = await db.execute(
        select(func.sum(EarningsRecord.gross_amount))
        .where(
            EarningsRecord.tradie_id == tradie_id,
            EarningsRecord.year      == year,
        )
    )
    ytd_gross = ytd_result.scalar() or 0.0

    # Simple deductions -- no pricing advice
    platform_fee = round(month_gross * PLATFORM_FEE, 2)
    gst_to_set_aside = round(month_gross * GST_RATE, 2)
    tax_buffer   = round((month_gross - platform_fee) * TAX_BUFFER_RATE, 2)
    take_home    = round(month_gross - platform_fee - gst_to_set_aside - tax_buffer, 2)

    # GST threshold tracking
    gst_pct     = round((ytd_gross / GST_THRESHOLD) * 100, 1)
    gst_warning = ytd_gross >= GST_THRESHOLD * 0.80

    return {
        "period": {
            "month": month,
            "year":  year,
        },
        "this_month": {
            "gross":            month_gross,
            "platform_fee":     platform_fee,
            "gst_to_set_aside": gst_to_set_aside,
            "tax_buffer":       tax_buffer,
            "take_home":        take_home,
        },
        "year_to_date": {
            "gross":             ytd_gross,
            "gst_threshold":     GST_THRESHOLD,
            "gst_threshold_pct": gst_pct,
        },
        "gst_warning":         gst_warning,
        "gst_warning_message": (
            f"You have reached {gst_pct}% of the $75,000 GST threshold. "
            f"Register for GST before you exceed this."
        ) if gst_warning else None,
    }


class EarningsNotPayableError(Exception):
    """Raised when the caller tries to book earnings on a job that hasn't reached
    a payable terminal state (i.e. still inside the dispute window, disputed,
    cancelled, etc.). The endpoint converts this into a 400."""
    pass


async def _job_is_payable(job_id: str, tradie_id: str, db: AsyncSession) -> tuple[bool, str]:
    """
    Decide whether a particular tradie may book earnings on a particular job.

    Rules (in order):
      1. The job must exist and be in status 'closed' -- the only state that
         guarantees the dispute window is fully closed and (if disputed) admin
         has signed off.
      2. The recording tradie must be the one who was actually hired -- i.e.
         they have a Lead row on the job. If anyone could record an earning on
         someone else's job, the ledger is meaningless.

    Returns: (ok, reason).
    """
    from models.job import Job
    from models.lead import Lead

    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        return False, "Job not found."
    if job.is_deleted:
        return False, "Job has been deleted."
    if job.status != "closed":
        return False, (
            f"Earnings can only be booked on closed jobs. "
            f"This job is currently '{job.status}'. "
            f"Wait until the 48-hour dispute window closes (or an admin resolves any dispute) before recording earnings."
        )

    lead_res = await db.execute(
        select(Lead).where(Lead.job_id == job_id, Lead.tradie_id == tradie_id)
    )
    if not lead_res.scalar_one_or_none():
        return False, "You were not the tradie assigned to this job."

    return True, ""


async def _earning_already_booked(job_id: str, tradie_id: str, db: AsyncSession) -> bool:
    """Idempotency check -- avoid double-booking when both the manual endpoint
    and the auto-close beat task try to record the same earning."""
    res = await db.execute(
        select(EarningsRecord.id).where(
            EarningsRecord.job_id    == job_id,
            EarningsRecord.tradie_id == tradie_id,
        )
    )
    return res.scalar_one_or_none() is not None


async def record_earning(
    tradie_id:    str,
    job_id:       str,
    gross_amount: float,
    db:           AsyncSession,
    *,
    enforce_payable: bool = True,
) -> EarningsRecord:
    """
    Book an earning for a tradie on a job.

    enforce_payable=True (the default) runs the strict status + ownership
    checks above. Pass False ONLY from system-internal callers (e.g. the
    auto-close beat task) that have already verified the job is closed.
    """
    if gross_amount <= 0:
        raise EarningsNotPayableError("Gross amount must be greater than zero.")

    if enforce_payable:
        ok, reason = await _job_is_payable(job_id, tradie_id, db)
        if not ok:
            raise EarningsNotPayableError(reason)

    # Idempotency -- never double-book a (tradie, job) earning.
    if await _earning_already_booked(job_id, tradie_id, db):
        existing_res = await db.execute(
            select(EarningsRecord).where(
                EarningsRecord.job_id    == job_id,
                EarningsRecord.tradie_id == tradie_id,
            )
        )
        return existing_res.scalar_one()

    now          = datetime.utcnow()
    platform_fee = round(gross_amount * PLATFORM_FEE, 2)
    gst_amount   = round(gross_amount * GST_RATE, 2)
    tax_buffer   = round((gross_amount - platform_fee) * TAX_BUFFER_RATE, 2)
    net_estimate = round(gross_amount - platform_fee - gst_amount - tax_buffer, 2)

    record = EarningsRecord(
        tradie_id    = tradie_id,
        job_id       = job_id,
        month        = now.month,
        year         = now.year,
        gross_amount = gross_amount,
        platform_fee = platform_fee,
        gst_amount   = gst_amount,
        tax_buffer   = tax_buffer,
        net_estimate = net_estimate,
    )
    db.add(record)
    await db.flush()
    return record
