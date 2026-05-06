from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.user import User, UserRole
from schemas.user_schema import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from services.auth_service import hash_password, verify_password, create_access_token
from services.otp_service import generate_and_send, verify, can_resend
from pydantic import BaseModel
import uuid


class VerifyOTPRequest(BaseModel):
    code: str

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account.
    Idempotent for unverified emails: allows updating details and resending OTP.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    existing = result.scalar_one_or_none()

    if existing:
        if existing.email_verified:
            # Fully registered user — must sign in
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists. Please sign in.",
            )
        else:
            # Started registration but never finished OTP — allow retry/update
            existing.hashed_password = hash_password(body.password)
            existing.full_name = body.full_name
            if body.phone:
                existing.phone = body.phone
            existing.role = body.role.value
            await db.commit()
            await db.refresh(existing)
            # Resend OTP
            await generate_and_send(db, existing)
            return existing

    # ── New user ──────────────────────────────────────────────────────────────
    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower(),
        phone=body.phone,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role.value,
        email_verified=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Automatically trigger the first OTP (prints to console)
    await generate_and_send(db, user)

    return user

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Strict role-locking: each login page sends its expected role.
    # Friendly redirect message tells the user which login to use.
    if body.expected_role and body.expected_role != user.role:
        if user.role == "tradie":
            msg = "This account is registered as a tradie. Please use the tradie login page."
        else:
            msg = "This account is registered as a homeowner. Please use the homeowner login page."
        raise HTTPException(status_code=403, detail=msg)

    token = create_access_token({"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


from services.auth_service import get_current_user
from models.user import User

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/send-email-otp", status_code=200)
async def send_email_otp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a fresh email OTP and send via Resend.
    Rate-limited: 60s between sends.
    Idempotent — the latest unused OTP is invalidated when a new one is created.
    """
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
    """Verify the OTP submitted by the user."""
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
    """Alias for send-email-otp — clearer client-side semantics."""
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