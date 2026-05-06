from fastapi import APIRouter, Depends, HTTPException
from services.storage_service import generate_presigned_upload_url
from services.auth_service import get_current_user, get_optional_user
from models.user import User
from models.job_photo import JobPhoto
from models.job import Job
from db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
import os

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "image/heic", "image/heif",
}

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg":  "jpg",
    "image/png":  "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


# ── Presign ──────────────────────────────────────────────────────────────────
# Frontend sends: { filename, content_type, context }
# Backend returns: { upload_url, key, public_url }

class PresignRequest(BaseModel):
    filename:     str
    content_type: str
    context:      Optional[str] = "job_photo"   # frontend always sends "job_photo"
    job_id:       Optional[str] = None           # optional — may not exist yet


@router.post("/presign")
async def get_presigned_url(
    body: PresignRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a presigned PUT URL so the browser can upload directly to R2/S3.

    This endpoint intentionally does NOT require job_id — the wizard uploads
    photos on Step 2, before the job is created at Step 5.  Photos are linked
    to the job later via /confirm once the job_id is known.
    """
    content_type = body.content_type.lower().split(";")[0].strip()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: JPEG, PNG, WEBP, HEIC",
        )

    ext = MIME_TO_EXT.get(content_type, "jpg")

    user_id = current_user.id if current_user else "anonymous"
    folder = f"jobs/{body.job_id}" if body.job_id else f"uploads/temp/{user_id}"

    try:
        result = generate_presigned_upload_url(
            folder=folder,
            file_extension=ext,
            content_type=content_type,
        )
        # Map backend field names → what the frontend expects
        return {
            "upload_url": result["upload_url"],
            "key":        result["file_key"],
            "public_url": result["file_url"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")


# ── Confirm ──────────────────────────────────────────────────────────────────
# Frontend sends: { key }  (without job_id during wizard)
# Or later:       { key, job_id }  (to attach photo to a specific job)

class ConfirmUpload(BaseModel):
    key:    str
    job_id: Optional[str] = None
    url:    Optional[str] = None


@router.post("/confirm")
async def confirm_upload(
    body: ConfirmUpload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save an uploaded photo record.

    - If job_id is provided: verify ownership and create a JobPhoto row.
    - If job_id is absent:   just acknowledge the upload (photo will be linked later).
    """
    if body.job_id:
        # Verify job ownership
        result = await db.execute(select(Job).where(Job.id == body.job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.homeowner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your job")

        # Build public URL from key
        public_url = body.url if body.url else _key_to_public_url(body.key)

        photo = JobPhoto(
            id=str(uuid.uuid4()),
            job_id=body.job_id,
            url=public_url,
            file_key=body.key,
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)
        return {"id": photo.id, "url": photo.url, "key": body.key}

    # No job_id yet — just acknowledge; nothing to persist yet
    return {"key": body.key, "status": "pending_job_assignment"}


# ── Photos for a job ─────────────────────────────────────────────────────────

@router.get("/job/{job_id}/photos")
async def get_job_photos(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobPhoto).where(JobPhoto.job_id == job_id)
        .order_by(JobPhoto.created_at.asc())
    )
    photos = result.scalars().all()
    return [{"id": p.id, "url": p.url, "key": p.file_key} for p in photos]


# ── Helper ───────────────────────────────────────────────────────────────────

def _key_to_public_url(key: str) -> str:
    """Build public CDN URL from an R2 object key."""
    from dotenv import load_dotenv
    load_dotenv()
    base = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{key}"