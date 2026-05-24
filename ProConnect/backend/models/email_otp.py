"""
backend/models/email_otp.py

Stores email OTP codes for verification.
- 6-digit code, 10-minute expiry
- Max 5 attempts before lockout
- Marked as used after successful verification
- Old/used codes cleaned by a periodic Celery task (not built yet — manual cleanup OK for now)
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base


class EmailOTP(Base):
    __tablename__ = "email_otps"

    id          : Mapped[str]      = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     : Mapped[str]      = mapped_column(String,      ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code        : Mapped[str]      = mapped_column(String(6),   nullable=False)
    expires_at  : Mapped[datetime] = mapped_column(DateTime,    nullable=False)
    attempts    : Mapped[int]      = mapped_column(Integer,     default=0, nullable=False)
    used_at     : Mapped[datetime] = mapped_column(DateTime,    nullable=True)
    created_at  : Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Quick lookup of latest unused code for a user
        Index("ix_email_otps_user_used", "user_id", "used_at"),
    )