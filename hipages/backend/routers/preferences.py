"""
backend/routers/preferences.py  — REPLACE the previous version entirely.

Key fix: prefix is now /api/v1/tradies/preferences to match the axios
base URL (http://localhost:8000/api/v1) used throughout the frontend.

Routes:
  GET  /api/v1/tradies/preferences/me
  PATCH /api/v1/tradies/preferences/me
"""
import uuid
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db.session import get_db
from models.tradie_profile import TradieProfile
from models.tradie_preference import TradiePreference
from models.user import User
from services.auth_service import get_current_user

# ── PREFIX MATCHES AXIOS BASE URL (/api/v1) ───────────────────────────────────
router = APIRouter(prefix="/api/v1/tradies/preferences", tags=["Tradie Preferences"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ServiceSuburb(BaseModel):
    suburb:     str
    postcode:   str
    state_code: str


class PreferenceUpdate(BaseModel):
    accept_residential : Optional[bool]                = None
    accept_commercial  : Optional[bool]                = None
    accept_high_intent : Optional[bool]                = None
    accept_planning    : Optional[bool]                = None
    notify_new_lead    : Optional[bool]                = None
    notify_email       : Optional[bool]                = None
    notify_sms         : Optional[bool]                = None
    service_suburbs    : Optional[List[ServiceSuburb]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_suburbs(raw: str | None) -> list:
    if not raw: return []
    try: return json.loads(raw)
    except: return []

def _serialize_suburbs(suburbs):
    if not suburbs:
        return None
    out = []
    for s in suburbs:
        if hasattr(s, "model_dump"):
            out.append(s.model_dump())   # Pydantic model
        elif isinstance(s, dict):
            out.append(s)                # Plain dict from request body
        else:
            out.append(dict(s))          # SQLAlchemy row or similar
    return json.dumps(out)


def _to_dict(pref: TradiePreference) -> dict:
    return {
        "accept_residential" : pref.accept_residential,
        "accept_commercial"  : pref.accept_commercial,
        "accept_high_intent" : pref.accept_high_intent,
        "accept_planning"    : pref.accept_planning,
        "notify_new_lead"    : pref.notify_new_lead,
        "notify_email"       : pref.notify_email,
        "notify_sms"         : pref.notify_sms,
        "service_suburbs"    : _parse_suburbs(pref.service_suburbs),
    }


async def _get_profile(user_id: str, db: AsyncSession) -> TradieProfile:
    result = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Tradie profile not found. Create your profile first.")
    return profile


async def _get_or_create_pref(tradie_id: str, db: AsyncSession) -> TradiePreference:
    result = await db.execute(select(TradiePreference).where(TradiePreference.tradie_id == tradie_id))
    pref = result.scalar_one_or_none()
    if not pref:
        pref = TradiePreference(
            id=str(uuid.uuid4()),
            tradie_id=tradie_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_preferences(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    profile = await _get_profile(current_user.id, db)
    pref    = await _get_or_create_pref(profile.id, db)
    return _to_dict(pref)


@router.patch("/me")
async def update_my_preferences(
    body:         PreferenceUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    profile = await _get_profile(current_user.id, db)
    pref    = await _get_or_create_pref(profile.id, db)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "service_suburbs":
            if value is not None and len(value) > 20:
                raise HTTPException(status_code=422, detail="Maximum 20 service areas allowed.")
            setattr(pref, "service_suburbs", _serialize_suburbs(value) if value is not None else None)
        else:
            setattr(pref, field, value)

    pref.updated_at = datetime.utcnow()
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return _to_dict(pref)