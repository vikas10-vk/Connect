# =============================================================================
# security.py — JWT tokens, refresh rotation, auth dependencies
# Tradie Platform
# =============================================================================
#
# FIX APPLIED: Dummy hash for timing attack prevention.
#
# PROBLEM: "$2b$12$dummyhashXXX..." is not a valid bcrypt hash.
# passlib may fail it faster than a real verification, restoring the timing
# difference that lets attackers detect whether an email exists.
#
# FIX: Pre-compute a real bcrypt hash at module import time.
# Cost: ~250ms once at startup. After that it's a constant.
# =============================================================================

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

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
# 1. Password hashing
# =============================================================================

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Pre-computed bcrypt hash for timing attack prevention.
#
# WHY THIS EXISTS:
# When a login attempt uses an email that doesn't exist in the database,
# we must still run a bcrypt verification (even though we have nothing to
# verify against) to make the response take the same ~250ms as a real
# verification. Without this, the response is immediate for unknown emails
# — a timing oracle that tells attackers which emails are registered.
#
# WHY NOT A HARDCODED STRING:
# The previous version used "$2b$12$dummyhashXXX..." which is not a valid
# bcrypt hash. passlib may reject it faster than a real verification,
# restoring the timing difference. We use a real pre-computed hash.
#
# COST: ~250ms once at module import time. Negligible in practice.
_DUMMY_HASH: str = _pwd_context.hash("__tradie_dummy_timing_hash_never_matches__")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify password. Always takes ~250ms regardless of outcome.
    Compatible with hashes made by direct bcrypt.hashpw() and by passlib.
    Both produce $2b$ format — fully interoperable.
    """
    return _pwd_context.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    return _pwd_context.needs_update(hashed)


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
        "sub": str(user_id),
        "role": role,
        "verified": is_verified,
        "active": is_active,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=EXPIRE_MINS),
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
        "sub": str(user_id),
        "type": "refresh",
        "jti": token_id,
        "family": family_id,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_EXPIRE_DAYS),
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
# 4. FastAPI auth dependencies (new routers only)
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