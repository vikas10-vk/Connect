from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.user import User
from models.tradie_profile import TradieProfile
from services.auth_service import get_current_user
from services.earnings_service import get_monthly_summary, record_earning
from pydantic import BaseModel

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
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    result = await db.execute(
        select(TradieProfile).where(TradieProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")

    record = await record_earning(profile.id, body.job_id, body.gross_amount, db)
    return {"id": record.id, "net_estimate": record.net_estimate}