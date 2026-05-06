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

    # Simple deductions — no pricing advice
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


async def record_earning(
    tradie_id:    str,
    job_id:       str,
    gross_amount: float,
    db:           AsyncSession,
) -> EarningsRecord:
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
    await db.commit()
    return record


