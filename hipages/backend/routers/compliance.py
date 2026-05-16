from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.user import User
from models.tradie_pass import TradiePass
from models.tradie_preference import TradiePreference
from models.tradie_profile import TradieProfile
from services.auth_service import get_current_user
from services.abn_service import lookup_abn
from services.compliance_service import calculate_pass_score, calculate_badge, get_licence_requirements
from services.storage_service import generate_presigned_upload_url
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
import uuid

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])


# ── Get or create TradiePASS ──────────────────────────────────
async def get_or_create_pass(tradie_id: str, db: AsyncSession) -> TradiePass:
    result = await db.execute(select(TradiePass).where(TradiePass.tradie_id == tradie_id))
    tp     = result.scalar_one_or_none()
    if not tp:
        tp = TradiePass(id=str(uuid.uuid4()), tradie_id=tradie_id)
        db.add(tp)
        await db.commit()
        await db.refresh(tp)
    return tp


async def get_tradie_profile(user: User, db: AsyncSession) -> TradieProfile:
    result  = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found")
    return profile


def _recalculate(tp: TradiePass, review_count: int = 0) -> TradiePass:
    tp.pass_score   = calculate_pass_score(tp)
    tp.badge_level  = calculate_badge(tp.pass_score, review_count, 0.9)
    return tp


# ── GET my TradiePASS ─────────────────────────────────────────
@router.get("/my-pass")
async def get_my_pass(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")
    profile = await get_tradie_profile(current_user, db)
    tp      = await get_or_create_pass(profile.id, db)
    return _serialize_pass(tp)


# ── Verify ABN ────────────────────────────────────────────────
class ABNRequest(BaseModel):
    abn: str

@router.post("/verify-abn")
async def verify_abn(
    body: ABNRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    profile = await get_tradie_profile(current_user, db)
    result  = await lookup_abn(body.abn)

    tp      = await get_or_create_pass(profile.id, db)
    tp.abn  = body.abn

    if result["valid"]:
        tp.abn_verified    = True
        tp.abn_name        = result.get("name", "")
        tp.abn_status      = result.get("status", "Active")
        tp.abn_verified_at = datetime.utcnow()
    else:
        tp.abn_verified = False
        tp.abn_status   = result.get("status", "Invalid")

    _recalculate(tp)
    await db.commit()
    await db.refresh(tp)

    return {
        "abn_result":  result,
        "pass_score":  tp.pass_score,
        "badge_level": tp.badge_level,
    }


# ── Update licence details ────────────────────────────────────
class LicenceUpdate(BaseModel):
    licence_number: str
    licence_type:   str
    licence_state:  str
    licence_expiry: date

@router.post("/update-licence")
async def update_licence(
    body: LicenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    profile               = await get_tradie_profile(current_user, db)
    tp                    = await get_or_create_pass(profile.id, db)
    tp.licence_number     = body.licence_number
    tp.licence_type       = body.licence_type
    tp.licence_state      = body.licence_state
    tp.licence_expiry     = body.licence_expiry
    tp.licence_verified   = True

    _recalculate(tp)
    await db.commit()
    await db.refresh(tp)
    return _serialize_pass(tp)


# ── Update insurance details ──────────────────────────────────
class InsuranceUpdate(BaseModel):
    pli_insurer:   str
    pli_amount_m:  float
    pli_expiry:    date
    wc_insurer:    Optional[str] = None
    wc_expiry:     Optional[date] = None

@router.post("/update-insurance")
async def update_insurance(
    body: InsuranceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    profile         = await get_tradie_profile(current_user, db)
    tp              = await get_or_create_pass(profile.id, db)
    tp.pli_insurer  = body.pli_insurer
    tp.pli_amount_m = body.pli_amount_m
    tp.pli_expiry   = body.pli_expiry
    tp.pli_verified = True

    if body.wc_insurer:
        tp.wc_insurer  = body.wc_insurer
        tp.wc_expiry   = body.wc_expiry
        tp.wc_verified = True

    _recalculate(tp)
    await db.commit()
    await db.refresh(tp)
    return _serialize_pass(tp)


# ── Update White Card ─────────────────────────────────────────
class WhiteCardUpdate(BaseModel):
    white_card_number: str

@router.post("/update-white-card")
async def update_white_card(
    body: WhiteCardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    profile                   = await get_tradie_profile(current_user, db)
    tp                        = await get_or_create_pass(profile.id, db)
    tp.white_card_number      = body.white_card_number
    tp.white_card_verified    = True

    _recalculate(tp)
    await db.commit()
    await db.refresh(tp)
    return _serialize_pass(tp)


# ── Get presigned URL for document upload ─────────────────────
class DocPresignRequest(BaseModel):
    doc_type:       str   # licence | pli | wc | swms
    file_extension: str

@router.post("/presign-doc")
async def presign_doc(
    body: DocPresignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    allowed_types = {"licence", "pli", "wc", "swms"}
    if body.doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {allowed_types}")

    profile = await get_tradie_profile(current_user, db)
    urls    = generate_presigned_upload_url(
        folder        = f"compliance/{profile.id}/{body.doc_type}",
        file_extension= body.file_extension.lstrip(".")
    )
    return urls


# ── Confirm document upload ───────────────────────────────────
class DocConfirm(BaseModel):
    doc_type: str
    file_url: str

@router.post("/confirm-doc")
async def confirm_doc(
    body: DocConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Tradies only")

    profile = await get_tradie_profile(current_user, db)
    tp      = await get_or_create_pass(profile.id, db)

    if body.doc_type == "licence":
        tp.licence_doc_url  = body.file_url
        tp.licence_verified = True
    elif body.doc_type == "pli":
        tp.pli_doc_url  = body.file_url
        tp.pli_verified = True
    elif body.doc_type == "wc":
        tp.wc_doc_url  = body.file_url
        tp.wc_verified = True
    elif body.doc_type == "swms":
        tp.swms_doc_url    = body.file_url
        tp.swms_uploaded   = True
        tp.swms_updated_at = datetime.utcnow()

    _recalculate(tp)
    await db.commit()
    await db.refresh(tp)
    return _serialize_pass(tp)


# ── Get public TradiePASS for any tradie ──────────────────────
@router.get("/pass/{tradie_id}")
async def get_public_pass(tradie_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradiePass).where(TradiePass.tradie_id == tradie_id))
    tp     = result.scalar_one_or_none()
    if not tp:
        return {"pass_score": 0, "badge_level": "bronze", "verifications": {}}
    return _serialize_pass_public(tp)


def _serialize_pass(tp: TradiePass) -> dict:
    return {
        "id":               tp.id,
        "pass_score":       tp.pass_score,
        "badge_level":      tp.badge_level,
        "abn_verified":     tp.abn_verified,
        "abn":              tp.abn,
        "abn_name":         tp.abn_name,
        "licence_verified": tp.licence_verified,
        "licence_number":   tp.licence_number,
        "licence_type":     tp.licence_type,
        "licence_expiry":   str(tp.licence_expiry) if tp.licence_expiry else None,
        "pli_verified":     tp.pli_verified,
        "pli_amount_m":     tp.pli_amount_m,
        "pli_expiry":       str(tp.pli_expiry) if tp.pli_expiry else None,
        "wc_verified":      tp.wc_verified,
        "white_card_verified": tp.white_card_verified,
        "swms_uploaded":    tp.swms_uploaded,
        "swms_updated_at":  tp.swms_updated_at.isoformat() if tp.swms_updated_at else None,
        "licence_doc_url":  tp.licence_doc_url,
        "pli_doc_url":      tp.pli_doc_url,
        "wc_doc_url":       tp.wc_doc_url,
        "swms_doc_url":     tp.swms_doc_url,
    }


def _serialize_pass_public(tp: TradiePass) -> dict:
    """Public version — no doc URLs or sensitive numbers"""
    from datetime import date
    today = date.today()
    return {
        "pass_score":       tp.pass_score,
        "badge_level":      tp.badge_level,
        "abn_verified":     tp.abn_verified,
        "licence_verified": tp.licence_verified,
        "licence_expiry_valid": tp.licence_expiry > today if tp.licence_expiry else False,
        "pli_verified":     tp.pli_verified,
        "pli_expiry_valid": tp.pli_expiry > today if tp.pli_expiry else False,
        "pli_amount_m":     tp.pli_amount_m,
        "wc_verified":      tp.wc_verified,
        "white_card_verified": tp.white_card_verified,
        "swms_uploaded":    tp.swms_uploaded,
    }