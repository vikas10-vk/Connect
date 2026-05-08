# =============================================================================
# security.py — JWT tokens, refresh rotation, auth dependencies
# Tradie Platform
# =============================================================================
#
# CHANGE: Removed passlib — now uses bcrypt directly.
#
# WHY PASSLIB WAS REMOVED:
#   passlib 1.7.4 (last release: 2020) accesses bcrypt.__about__ to detect
#   the bcrypt version. bcrypt 4.0+ removed __about__ entirely.
#   Result: passlib crashes on import with modern bcrypt versions.
#   passlib is effectively abandoned — no fix will ever come.
#
# FIX:
#   Use bcrypt directly, exactly as auth_service.py already does.
#   hash_password() and verify_password() behave identically.
#   All existing password hashes in the database continue to work —
#   the hash format ($2b$12$...) is the same regardless of whether
#   bcrypt was called via passlib or directly.
#
# _DUMMY_HASH IS NOW LAZY:
#   Previously _DUMMY_HASH was computed at module import time, causing
#   a crash if bcrypt had any issue during startup.
#   Now get_dummy_hash() computes it on first call only.
#   Import of this module never calls bcrypt.
# =============================================================================

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt as _bcrypt
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RefreshTokenError,
    SuspendedAccountError,
    TokenExpiredError,
    UnverifiedAccountError,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

SECRET_KEY          = os.getenv("SECRET_KEY")
ALGORITHM           = os.getenv("ALGORITHM", "HS256")
EXPIRE_MINS         = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Add SECRET_KEY=<your-secret> to your .env file. "
        "Generate one: openssl rand -base64 48"
    )

RT_VALID  = "rt:valid:"
RT_USED   = "rt:used:"
RT_FAMILY = "rt:family:"


# =============================================================================
# 1. Password hashing — bcrypt directly (no passlib)
# =============================================================================

def hash_password(plain: str) -> str:
    """
    Hash a password with bcrypt rounds=12.
    Truncates to 72 bytes explicitly — bcrypt silently or noisily truncates
    depending on version. Being explicit is safer and clearer.
    Compatible with all existing hashes in the database.
    """
    return _bcrypt.hashpw(
        plain[:72].encode("utf-8"),
        _bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a password against its hash.
    Works on hashes created by this function, by auth_service.hash_password(),
    and by the old passlib-based hash_password() — all produce $2b$ format.
    """
    try:
        return _bcrypt.checkpw(
            plain[:72].encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except Exception:
        return False


# =============================================================================
# Dummy hash for timing attack prevention — LAZY INITIALISATION
#
# WHY LAZY:
#   Computing a bcrypt hash takes ~250ms. Doing this at module import time:
#   - Slows every startup by 250ms
#   - Crashes the app if bcrypt fails to initialise for any reason
#   - Runs even when no login endpoint is ever called (e.g. in tests
#     that only test database models)
#
# HOW IT WORKS:
#   First call to get_dummy_hash() computes and caches the hash.
#   Subsequent calls return the cached value instantly.
#   Used in the login handler when the email does not exist, to ensure
#   the response time is the same as a real failed login (~250ms).
# =============================================================================

_dummy_hash_cache: str | None = None


def get_dummy_hash() -> str:
    """
    Return a valid bcrypt hash for timing attack prevention.
    Computed once on first call, cached forever.
    """
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        _dummy_hash_cache = hash_password("__tradie_dummy_timing_placeholder__")
    return _dummy_hash_cache


# =============================================================================
# 2. Access tokens
# =============================================================================

def create_access_token(
    user_id: uuid.UUID | str,
    role: str,
    is_verified: bool = True,
    is_active: bool = True,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub":      str(user_id),
        "role":     role,
        "verified": is_verified,
        "active":   is_active,
        "type":     "access",
        "iat":      now,
        "exp":      now + timedelta(minutes=EXPIRE_MINS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise AuthenticationError("Invalid token")

    if payload.get("type") == "refresh":
        raise AuthenticationError("Invalid token type — use your access token")

    return payload


# =============================================================================
# 3. Refresh tokens
# =============================================================================

def create_refresh_token(
    user_id: uuid.UUID | str,
    family_id: str | None = None,
) -> tuple[str, str, str]:
    now       = datetime.now(UTC)
    token_id  = str(uuid.uuid4())
    family_id = family_id or str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub":    str(user_id),
        "type":   "refresh",
        "jti":    token_id,
        "family": family_id,
        "iat":    now,
        "exp":    now + timedelta(days=REFRESH_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, token_id, family_id


async def store_refresh_token(
    token_id: str,
    family_id: str,
    user_id: str,
    redis_client: Any,
) -> None:
    ttl = REFRESH_EXPIRE_DAYS * 86400
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.setex(f"{RT_VALID}{token_id}", ttl, user_id)
        pipe.sadd(f"{RT_FAMILY}{family_id}", token_id)
        pipe.expire(f"{RT_FAMILY}{family_id}", ttl)
        await pipe.execute()


async def rotate_refresh_token(
    token: str,
    redis_client: Any,
) -> tuple[str, str, str, str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise RefreshTokenError("Refresh token has expired. Please log in again.")
    except JWTError:
        raise RefreshTokenError("Invalid refresh token.")

    if payload.get("type") != "refresh":
        raise RefreshTokenError("Invalid token type.")

    token_id: str = payload.get("jti", "")
    family_id: str = payload.get("family", "")
    user_id: str   = payload.get("sub", "")

    if not all([token_id, family_id, user_id]):
        raise RefreshTokenError("Malformed refresh token.")

    is_valid = await redis_client.exists(f"{RT_VALID}{token_id}")
    is_used  = await redis_client.exists(f"{RT_USED}{token_id}")

    if not is_valid:
        if is_used:
            logger.critical(
                "Refresh token reuse detected — invalidating family",
                extra={"user_id": user_id, "family_id": family_id},
            )
            await _invalidate_family(family_id, redis_client)
            raise RefreshTokenError(
                "Session invalidated due to suspicious activity. Please log in again."
            )
        raise RefreshTokenError("Refresh token not found. Please log in again.")

    ttl = REFRESH_EXPIRE_DAYS * 86400
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.delete(f"{RT_VALID}{token_id}")
        pipe.setex(f"{RT_USED}{token_id}", ttl, "1")
        await pipe.execute()

    new_token, new_token_id, _ = create_refresh_token(user_id, family_id)
    await store_refresh_token(new_token_id, family_id, user_id, redis_client)
    return new_token, new_token_id, family_id, user_id


async def revoke_token_family(family_id: str, redis_client: Any) -> None:
    await _invalidate_family(family_id, redis_client)


async def _invalidate_family(family_id: str, redis_client: Any) -> None:
    token_ids = await redis_client.smembers(f"{RT_FAMILY}{family_id}")
    if token_ids:
        async with redis_client.pipeline(transaction=True) as pipe:
            for tid in token_ids:
                t = tid.decode() if isinstance(tid, bytes) else tid
                pipe.delete(f"{RT_VALID}{t}")
            pipe.delete(f"{RT_FAMILY}{family_id}")
            await pipe.execute()


# =============================================================================
# 4. FastAPI auth dependencies
# =============================================================================

_bearer = HTTPBearer(auto_error=False)


async def _get_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise AuthenticationError("Authorization header missing")
    payload = decode_access_token(credentials.credentials)
    if not payload.get("active", True):
        raise SuspendedAccountError()
    request.state.user_id = payload.get("sub")
    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(_get_payload),
) -> dict[str, Any]:
    return payload


async def get_current_verified_user(
    payload: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not payload.get("verified", False):
        raise UnverifiedAccountError()
    return payload


async def require_homeowner(
    payload: dict[str, Any] = Depends(get_current_verified_user),
) -> dict[str, Any]:
    if payload.get("role") != "homeowner":
        raise PermissionDeniedError("This action is only available to homeowners")
    return payload


async def require_tradie(
    payload: dict[str, Any] = Depends(get_current_verified_user),
) -> dict[str, Any]:
    if payload.get("role") != "tradie":
        raise PermissionDeniedError("This action is only available to tradies")
    return payload


# =============================================================================
# 5. IDOR protection
# =============================================================================

def assert_resource_owner(
    resource_owner_id: uuid.UUID | str,
    requesting_user_id: str,
    resource_name: str = "resource",
) -> None:
    if str(resource_owner_id) != str(requesting_user_id):
        logger.warning(
            "IDOR attempt blocked",
            extra={"resource": resource_name, "requester": requesting_user_id},
        )
        raise NotFoundError(resource_name)


# =============================================================================
# 6. Field encryption
# =============================================================================

def encrypt_field(value: str) -> str:
    if not value:
        return value
    key = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not key:
        return value
    return Fernet(key.encode()).encrypt(value.encode()).decode()


def decrypt_field(encrypted: str) -> str:
    if not encrypted:
        return encrypted
    key = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not key:
        return encrypted
    try:
        return Fernet(key.encode()).decrypt(encrypted.encode()).decode()
    except InvalidToken as e:
        logger.error("Field decryption failed")
        raise ValueError("Could not decrypt field") from e