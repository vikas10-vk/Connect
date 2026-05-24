import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.job import Job
from models.review import Review
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/reviews", tags=["Reviews"])

class ReviewCreate(BaseModel):
    job_id: str
    tradie_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None

class ReviewResponse(BaseModel):
    id: str
    job_id: str
    homeowner_id: str
    tradie_id: str
    rating: int
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    body: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "homeowner":
        raise HTTPException(status_code=403, detail="Only homeowners can leave reviews")

    # Verify job belongs to this homeowner
    result = await db.execute(select(Job).where(Job.id == body.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.homeowner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Can only review a completed job")

    # Check review doesn't already exist
    result = await db.execute(select(Review).where(Review.job_id == body.job_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Review already submitted")

    # Verify tradie exists
    tradie_result = await db.execute(select(TradieProfile).where(TradieProfile.id == body.tradie_id))
    if not tradie_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tradie not found")

    review = Review(
        id=str(uuid.uuid4()),
        job_id=body.job_id,
        homeowner_id=current_user.id,
        tradie_id=body.tradie_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review

@router.get("/tradie/{tradie_id}", response_model=list[ReviewResponse])
async def get_tradie_reviews(tradie_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review)
        .where(Review.tradie_id == tradie_id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()
