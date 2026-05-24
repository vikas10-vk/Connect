"""
backend/models/tradie_profile.py

Represents the BUSINESS that users book — solo or team. A solo tradie is
treated as a business of one for code uniformity (same code path).

UPDATED — adds:
  - rating_avg / rating_count          : aggregate rating cache, updated on review approval
  - verified_at                         : first time the business was approved (separate from reviewed_at)
  - logo_url / selfie_url               : business logo + owner's verified selfie (face-match check-in)
  - team_members                        : workers in the business (and the owner row for solo if created)
  - certifications                      : licence rows directly held by the solo tradie (NOT workers'
                                           certs — those live on TeamMember.certifications)
  - insurance_policies                  : business-level insurance (public liability, workers comp, etc.)

NOTE: existing fields are kept exactly as-is so nothing breaks.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class TradieProfile(Base):
    __tablename__ = "tradie_profiles"

    # ── Existing identity (UNCHANGED) ───────────────────────────────
    id:              Mapped[str]      = mapped_column(String,       primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:         Mapped[str]      = mapped_column(String,       ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    business_name:   Mapped[str]      = mapped_column(String(255),  nullable=False)
    abn:             Mapped[str]      = mapped_column(String(20),   nullable=True)
    bio:             Mapped[str]      = mapped_column(Text,         nullable=True)
    suburb:          Mapped[str]      = mapped_column(String(100),  nullable=True)
    state:           Mapped[str]      = mapped_column(String(50),   nullable=True)
    postcode:        Mapped[str]      = mapped_column(String(10),   nullable=True)
    lat:             Mapped[float]    = mapped_column(Float,        nullable=True)
    lng:             Mapped[float]    = mapped_column(Float,        nullable=True)
    radius_km:       Mapped[int]      = mapped_column(Integer,      default=25)
    is_available:    Mapped[bool]     = mapped_column(Boolean,      default=True)   # "Pause bookings" toggle (also clears Redis cache)
    credits:         Mapped[int]      = mapped_column(Integer,      default=0)

    avatar_url:      Mapped[str]      = mapped_column(String(500),  nullable=True)
    cover_photo_url: Mapped[str]      = mapped_column(String(500),  nullable=True)

    created_at:      Mapped[datetime] = mapped_column(DateTime,     default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Existing verification workflow (UNCHANGED) ──────────────────
    verification_status: Mapped[str]      = mapped_column(String(30),  default="pending_review", nullable=False, index=True)
    verification_notes : Mapped[str]      = mapped_column(Text,        nullable=True)
    reviewed_at        : Mapped[datetime] = mapped_column(DateTime,    nullable=True)
    reviewed_by        : Mapped[str]      = mapped_column(String,      nullable=True)   # admin user_id
    email_notified_at  : Mapped[datetime] = mapped_column(DateTime,    nullable=True)

    # ── Existing team structure (UNCHANGED) ─────────────────────────
    solo_or_team       : Mapped[str]      = mapped_column(String(10),  default="solo", nullable=False)   # 'solo' | 'team'
    team_size          : Mapped[str]      = mapped_column(String(10),  nullable=True)                    # '2-5' | '6-10' | '10+'

    # ── NEW: aggregated ratings (cached; recomputed on review approval) ─
    rating_avg   : Mapped[float] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count : Mapped[int]   = mapped_column(Integer,       default=0,    nullable=False)

    # ── NEW: verification + branding ────────────────────────────────
    verified_at : Mapped[datetime] = mapped_column(DateTime,    nullable=True)   # first approval timestamp
    logo_url    : Mapped[str]      = mapped_column(String(500), nullable=True)
    selfie_url  : Mapped[str]      = mapped_column(String(500), nullable=True)   # owner's verified selfie (face-match at check-in)

    # ── Relationships ───────────────────────────────────────────────
    user              = relationship("User",            back_populates="tradie_profile")
    tradie_categories = relationship("TradieCategory",  back_populates="tradie", cascade="all, delete-orphan")
    reviews           = relationship("Review",          back_populates="tradie", order_by="Review.created_at.desc()")

    team_members = relationship(
        "TeamMember",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    certifications = relationship(
        "TradieCertification",
        foreign_keys="TradieCertification.tradie_profile_id",
        back_populates="tradie_profile",
        cascade="all, delete-orphan",
    )

    insurance_policies = relationship(
        "InsurancePolicy",
        back_populates="tradie_profile",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TradieProfile {self.business_name} [{self.verification_status}]>"
