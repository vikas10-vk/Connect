"""
backend/services/otp_service.py

Business logic for email OTP lifecycle:
  - generate_and_send(user)        → create OTP row + send via Resend
  - verify(user, code)             → check code, mark used, set user.is_verified
  - can_resend(user)               → rate-limit guard (60s between sends)

Tunables at top.
"""
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.email_otp import EmailOTP
from models.user import User
from services.resend_service import send_otp_email

# ── Tunables ─────────────────────────────────────────────────────────────────
OTP_LENGTH         = 6
OTP_TTL_MINUTES    = 10
MAX_ATTEMPTS       = 5
RESEND_COOLDOWN_S  = 60   # seconds between OTP sends


def _generate_code() -> str:
    """Six-digit numeric code with leading-zero support."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


async def _latest_otp(db: AsyncSession, user_id: str) -> EmailOTP | None:
    res = await db.execute(
        select(EmailOTP)
        .where(EmailOTP.user_id == user_id)
        .order_by(desc(EmailOTP.created_at))
        .limit(1)
    )
    return res.scalar_one_or_none()


async def can_resend(db: AsyncSession, user_id: str) -> tuple[bool, int]:
    """
    Returns (allowed, seconds_remaining).
    Throttle: caller must wait RESEND_COOLDOWN_S seconds since last OTP creation.
    """
    last = await _latest_otp(db, user_id)
    if last is None:
        return True, 0

    elapsed = (datetime.utcnow() - last.created_at).total_seconds()
    if elapsed >= RESEND_COOLDOWN_S:
        return True, 0
    return False, int(RESEND_COOLDOWN_S - elapsed)


async def generate_and_send(db: AsyncSession, user: User) -> tuple[bool, str | None]:
    """
    Create a fresh OTP, persist it, send via Resend.
    Returns (success, error_message).
    """
    # Invalidate any active OTPs for this user (mark as used so they can't be replayed)
    res = await db.execute(
        select(EmailOTP).where(
            EmailOTP.user_id == user.id,
            EmailOTP.used_at.is_(None),
        )
    )
    for old in res.scalars().all():
        old.used_at = datetime.utcnow()
        db.add(old)

    code = _generate_code()
    otp = EmailOTP(
        id         = str(uuid.uuid4()),
        user_id    = user.id,
        code       = code,
        expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        attempts   = 0,
        created_at = datetime.utcnow(),
    )
    db.add(otp)
    await db.commit()

    # Send (failures don't roll back the OTP — code is in DB and printed to console)
    print(f"\n{'='*60}\n[AUTH] Verification code for {user.email}: {code}\n{'='*60}\n", flush=True)
    sent = await send_otp_email(user.email, code, user.full_name or "")
    if not sent:
        # Still return success because code is recorded — user can request resend
        return True, None
    return True, None


async def verify(db: AsyncSession, user: User, submitted_code: str) -> tuple[bool, str]:
    """
    Verify a submitted code. Returns (success, message).
    On success: marks OTP used, sets user.is_verified=True, commits.
    """
    submitted_code = (submitted_code or "").strip()
    if len(submitted_code) != OTP_LENGTH or not submitted_code.isdigit():
        return False, "Code must be 6 digits."

    otp = await _latest_otp(db, user.id)
    if otp is None:
        return False, "No verification code found. Request a new one."

    if otp.used_at is not None:
        return False, "This code has already been used. Request a new one."

    if otp.expires_at < datetime.utcnow():
        return False, "This code has expired. Request a new one."

    if otp.attempts >= MAX_ATTEMPTS:
        return False, "Too many attempts. Request a new code."

    if otp.code != submitted_code:
        otp.attempts += 1
        db.add(otp)
        await db.commit()
        remaining = MAX_ATTEMPTS - otp.attempts
        if remaining <= 0:
            return False, "Too many attempts. Request a new code."
        return False, f"Incorrect code. {remaining} {'attempt' if remaining == 1 else 'attempts'} remaining."

    # Success
    otp.used_at = datetime.utcnow()
    user.is_verified = True
    user.email_verified = True
    db.add(otp)
    db.add(user)
    await db.commit()
    return True, "Email verified."
