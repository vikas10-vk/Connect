# =============================================================================
# services/auth_service.py — Authentication service
# Tradie Platform
# =============================================================================
#
# FIX APPLIED: SECRET_KEY null check.
#
# PROBLEM: If SECRET_KEY was missing from .env, os.getenv returned None.
# python-jose does NOT error on jwt.encode(payload, None) — it encodes
# with a null key. These tokens verify with jwt.decode(token, None, ...).
# Result: authentication was silently disabled if the env var was missing.
#
# FIX: Explicit check at module load time. App refuses to start without it.
# =============================================================================

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db

# ── Required secrets — fail fast if missing ───────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "The application cannot authenticate users without it. "
        "Add SECRET_KEY=<your-secret> to your .env file. "
        "Generate one: openssl rand -base64 48"
    )

ALGORITHM   = os.getenv("ALGORITHM", "HS256")
EXPIRE_MINS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


# =============================================================================
# Password utilities
# =============================================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# =============================================================================
# Token utilities
# =============================================================================

def create_access_token(data: dict) -> str:
    payload = data.copy()
    # Use timezone-aware datetime — datetime.utcnow() is deprecated in Python 3.12
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# =============================================================================
# FastAPI auth dependencies
# =============================================================================

bearer_scheme          = HTTPBearer()
bearer_scheme_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate Bearer token and return the User ORM object.
    Used by all existing 16 routers.
    Returns: User instance (use user.id, user.role, user.email, etc.)
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the User if a valid token is provided, None otherwise."""
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except Exception:
        return None

    from models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user and not user.is_active:
        return None
    return user