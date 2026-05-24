"""
backend/routers/preferences.py  — REPLACE the previous version entirely.

Key fix: prefix is now /api/v1/tradies/preferences to match the axios
base URL (http://localhost:8000/api/v1) used throughout the frontend.

Routes:
  GET  /api/v1/tradies/preferences/me
  PATCH /api/v1/tradies/preferences/me
"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.tradie_preference import TradiePreference
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user
from services.tradie_change_requests import (
    TradieChangeRequestType,
    create_pending_change_request,
)

# ── PREFIX MATCHES AXIOS BASE URL (/api/v1) ───────────────────────────────────
router = APIRouter(prefix="/api/v1/tradies/preferences", tags=["Tradie Preferences"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ServiceSuburb(BaseModel):
    suburb:     str
    postcode:   str
    state_code: str


class PreferenceUpdate(BaseModel):
    accept_residential : bool | None                = None
    accept_commercial  : bool | None                = None
    accept_high_intent : bool | None                = None
    accept_planning    : bool | None                = None
    notify_new_lead    : bool | None                = None
    notify_email       : bool | None                = None
    notify_sms         : bool | None                = None
    service_suburbs    : list[ServiceSuburb] | None = None


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


def _same_suburbs(a, b) -> bool:
    return json.dumps(a or [], sort_keys=True) == json.dumps(b or [], sort_keys=True)


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
    protected_change_requested = False
    for field, value in updates.items():
        if field == "service_suburbs":
            if value is not None and len(value) > 20:
                raise HTTPException(status_code=422, detail="Maximum 20 service areas allowed.")
            current_suburbs = _parse_suburbs(pref.service_suburbs)
            requested_suburbs = [
                s.model_dump() if hasattr(s, "model_dump") else dict(s)
                for s in (value or [])
            ]
            if profile.verification_status == "verified" and not _same_suburbs(current_suburbs, requested_suburbs):
                await create_pending_change_request(
                    db,
                    tradie_id=profile.id,
                    requested_by=current_user.id,
                    request_type=TradieChangeRequestType.SERVICE_AREAS,
                    payload={
                        "current_service_suburbs": current_suburbs,
                        "requested_service_suburbs": requested_suburbs,
                    },
                    note="Verified tradie requested service area update.",
                )
                protected_change_requested = True
                continue
            pref.service_suburbs = _serialize_suburbs(value) if value is not None else None
        else:
            setattr(pref, field, value)

    pref.updated_at = datetime.utcnow()
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    response = _to_dict(pref)
    if protected_change_requested:
        response["pending_admin_review"] = True
        response["message"] = "Service area changes were sent to admin for review."
    return response
