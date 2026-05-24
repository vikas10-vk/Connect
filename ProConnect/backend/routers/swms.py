import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.swms_document import SWMSDocument
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user
from services.swms_service import generate_swms_text, generate_swms_with_ai

router = APIRouter(prefix="/api/v1/swms", tags=["SWMS"])


class SWMSRequest(BaseModel):
    job_type:        str
    state:           str
    job_description: str | None = ""
    job_id:          str | None = None
    use_ai:          bool | None = True


@router.post("/generate")
async def generate_swms(
    body: SWMSRequest,
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

    # Generate content
    if body.use_ai:
        content = await generate_swms_with_ai(
            job_type        = body.job_type,
            state           = body.state,
            tradie_name     = current_user.full_name,
            business_name   = profile.business_name or current_user.full_name,
            job_description = body.job_description or "",
        )
    else:
        content = generate_swms_text(
            job_type        = body.job_type,
            state           = body.state,
            tradie_name     = current_user.full_name,
            business_name   = profile.business_name or current_user.full_name,
            job_description = body.job_description or "",
        )

    # Save to DB
    doc = SWMSDocument(
        id        = str(uuid.uuid4()),
        tradie_id = profile.id,
        job_id    = body.job_id,
        job_type  = body.job_type,
        state     = body.state,
        content   = content,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id":      doc.id,
        "content": doc.content,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/my-documents")
async def get_my_swms(
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
        return []

    docs_result = await db.execute(
        select(SWMSDocument)
        .where(SWMSDocument.tradie_id == profile.id)
        .order_by(SWMSDocument.created_at.desc())
    )
    docs = docs_result.scalars().all()
    return [
        {
            "id":         d.id,
            "job_type":   d.job_type,
            "state":      d.state,
            "doc_url":    d.doc_url,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]
