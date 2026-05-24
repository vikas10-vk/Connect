from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user
from services.earnings_service import (
    EarningsNotPayableError,
    get_monthly_summary,
    record_earning,
)

router = APIRouter(prefix="/api/v1/earnings", tags=["Earnings"])


@router.get("/summary")
async def earnings_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    return await get_monthly_summary(profile.id, db)


class RecordEarningRequest(BaseModel):
    job_id:       str
    gross_amount: float


@router.post("/record")
async def record(
    body: RecordEarningRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Book an earning for a closed job.

    Most earnings are auto-booked by the auto-close beat task when a job
    transitions to 'closed'. This endpoint exists as a fallback / manual
    correction tool. The earnings_service enforces:
      * job must be in status 'closed' (dispute window passed)
      * the recording tradie must be the one who was actually hired
      * (job_id, tradie_id) earnings are idempotent -- second call is a no-op
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    try:
        rec = await record_earning(profile.id, body.job_id, body.gross_amount, db)
    except EarningsNotPayableError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    return {"id": rec.id, "net_estimate": rec.net_estimate}
