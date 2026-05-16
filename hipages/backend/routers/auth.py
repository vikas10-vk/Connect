import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import ExpiredSignatureError, JWTError
from jose import jwt as _jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.user import User, UserRole
from schemas.user_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from security import (
    get_dummy_hash,
    create_refresh_token,
    revoke_token_family,
    rotate_refresh_token,
    store_refresh_token,
)
from services.auth_service import (
    create_access_token as legacy_create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.otp_service import can_resend, generate_and_send, verify


# =============================================================================
# Constants
# =============================================================================

MAX_LOGIN_ATTEMPTS          = int(os.getenv("AUTH_MAX_ATTEMPTS", "5"))
LOCKOUT_SECONDS             = int(os.getenv("AUTH_LOCKOUT_SECONDS", "900"))
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")) * 60
SECRET_KEY                  = os.getenv("SECRET_KEY")
ALGORITHM                   = os.getenv("ALGORITHM", "HS256")

_FAIL_KEY          = "login:fail:"
_LOCKED_KEY        = "login:locked:"
_USER_FAMILIES_KEY = "rt:user:"

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class VerifyOTPRequest(BaseModel):
    code: str


# =============================================================================
# Brute-force helpers
# =============================================================================

async def _check_brute_force(email: str, redis_client) -> None:
    locked = await redis_client.exists(f"{_LOCKED_KEY}{email}")
    if locked:
        ttl = await redis_client.ttl(f"{_LOCKED_KEY}{email}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {max(ttl, 1)} seconds.",
            headers={"Retry-After": str(max(ttl, 1))},
        )


async def _record_login_failure(email: str, redis_client) -> None:
    fail_key   = f"{_FAIL_KEY}{email}"
    locked_key = f"{_LOCKED_KEY}{email}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(fail_key)
        pipe.expire(fail_key, LOCKOUT_SECONDS)
        results = await pipe.execute()
    if results[0] >= MAX_LOGIN_ATTEMPTS:
        await redis_client.setex(locked_key, LOCKOUT_SECONDS, "1")


async def _clear_login_failures(email: str, redis_client) -> None:
    await redis_client.delete(f"{_FAIL_KEY}{email}")
    await redis_client.delete(f"{_LOCKED_KEY}{email}")


async def _track_user_family(user_id: str, family_id: str, redis_client) -> None:
    key     = f"{_USER_FAMILIES_KEY}{user_id}"
    ttl_sec = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")) * 86400
    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.sadd(key, family_id)
        pipe.expire(key, ttl_sec)
        await pipe.execute()


# =============================================================================
# POST /register — UNCHANGED
# =============================================================================

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    existing = result.scalar_one_or_none()

    if existing:
        if existing.email_verified:
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists. Please sign in.",
            )
        else:
            # FIX: also reject unverified duplicates.
            # The user registered but never verified — tell them to check their inbox.
            # Previously this silently re-registered and returned 201, which caused
            # test_register_duplicate_email_rejected to fail (expected 400, got 201).
            raise HTTPException(
                status_code=400,
                detail=(
                    "An account with this email is pending verification. "
                    "Please check your inbox for the verification code."
                ),
            )

    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower(),
        phone=body.phone,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role.value,
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await generate_and_send(db, user)
    return user


# =============================================================================
# POST /login — UPDATED
# =============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    redis_client = request.app.state.redis_client
    email_lower  = body.email.lower()

    await _check_brute_force(email_lower, redis_client)

    result = await db.execute(select(User).where(User.email == email_lower))
    user = result.scalar_one_or_none()

    # FIX: Use _DUMMY_HASH from security.py — a real pre-computed bcrypt hash.
    # The previous version used an invalid hash string which may have failed
    # faster than a real verification, revealing whether the email exists.
    password_ok = verify_password(
        body.password,
        user.hashed_password if user else get_dummy_hash(),
    )

    if not user or not password_ok:
        if user:
            await _record_login_failure(email_lower, redis_client)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if body.expected_role and body.expected_role != user.role:
        msg = (
            "This account is registered as a tradie. Please use the tradie login page."
            if user.role == "tradie"
            else "This account is registered as a homeowner. Please use the homeowner login page."
        )
        raise HTTPException(status_code=403, detail=msg)

    await _clear_login_failures(email_lower, redis_client)

    access_token = legacy_create_access_token({
        "sub":  user.id,
        "role": user.role,
        "jti":  str(uuid.uuid4()),   # ← guarantees uniqueness across calls
    })

    refresh_token, token_id, family_id = create_refresh_token(user_id=user.id)
    await store_refresh_token(
        token_id=token_id, family_id=family_id,
        user_id=user.id, redis_client=redis_client,
    )
    await _track_user_family(user.id, family_id, redis_client)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
    )


# =============================================================================
# POST /refresh — NEW
# =============================================================================

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    redis_client = request.app.state.redis_client

    new_refresh, new_token_id, family_id, user_id = await rotate_refresh_token(
        token=body.refresh_token, redis_client=redis_client,
    )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User account not found")

    if not user.is_active:
        await revoke_token_family(family_id=family_id, redis_client=redis_client)
        raise HTTPException(status_code=403, detail="Account is disabled")

    new_access = legacy_create_access_token({
        "sub":  user.id,
        "role": user.role,
        "jti":  str(uuid.uuid4()),   # ← guarantees new token every refresh
    })

    return RefreshResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
    )


# =============================================================================
# POST /logout — FIXED: ownership verification added
# =============================================================================

@router.post("/logout", status_code=200)
async def logout(
    request: Request,
    body: LogoutRequest,
    current_user: User = Depends(get_current_user),
):
    redis_client = request.app.state.redis_client

    try:
        payload   = _jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        family_id = payload.get("family")
        token_sub = payload.get("sub")

        # FIX: Verify the refresh token belongs to the authenticated user.
        #
        # ATTACK PREVENTED:
        # Attacker with access_token(UserA) + refresh_token(UserB) calls /logout.
        # Without this check: UserB's session is silently revoked.
        # With this check: the mismatch is detected and we return success without
        # revoking anything — we do NOT reveal that the token belongs to someone else.
        #
        # We return the same "logged out" response either way — security through
        # consistent responses, no information leakage.
        if token_sub != str(current_user.id):
            # Silently succeed — don't reveal the token belongs to someone else.
            return {"logged_out": True, "message": "Logged out successfully"}

        if family_id:
            await revoke_token_family(family_id=family_id, redis_client=redis_client)

    except (ExpiredSignatureError, JWTError):
        # Already expired or invalid — effectively already logged out.
        pass

    return {"logged_out": True, "message": "Logged out successfully"}


# =============================================================================
# POST /logout-all — NEW (unchanged from previous version)
# =============================================================================

@router.post("/logout-all", status_code=200)
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    redis_client      = request.app.state.redis_client
    user_families_key = f"{_USER_FAMILIES_KEY}{current_user.id}"

    family_ids    = await redis_client.smembers(user_families_key)
    revoked_count = 0

    for fid in family_ids:
        family_id = fid.decode() if isinstance(fid, bytes) else fid
        await revoke_token_family(family_id=family_id, redis_client=redis_client)
        revoked_count += 1

    await redis_client.delete(user_families_key)

    return {
        "logged_out": True,
        "sessions_revoked": revoked_count,
        "message": f"Logged out from {revoked_count} device(s) successfully",
    }


# =============================================================================
# UNCHANGED endpoints below
# =============================================================================

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/send-email-otp", status_code=200)
async def send_email_otp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"already_verified": True, "message": "Your email is already verified."}
    allowed, wait_s = await can_resend(db, current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {wait_s} seconds before requesting another code.",
        )
    success, err = await generate_and_send(db, current_user)
    if not success:
        raise HTTPException(status_code=500, detail=err or "Could not send code. Try again.")
    return {"sent": True, "message": "Verification code sent. Check your inbox."}


@router.post("/verify-email-otp", status_code=200)
async def verify_email_otp(
    body: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"verified": True, "message": "Email already verified."}
    success, message = await verify(db, current_user, body.code)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"verified": True, "message": message}


@router.post("/resend-email-otp", status_code=200)
async def resend_email_otp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"already_verified": True, "message": "Your email is already verified."}
    allowed, wait_s = await can_resend(db, current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {wait_s} seconds before requesting another code.",
        )
    success, err = await generate_and_send(db, current_user)
    if not success:
        raise HTTPException(status_code=500, detail=err or "Could not send code. Try again.")
    return {"sent": True, "message": "New verification code sent."}