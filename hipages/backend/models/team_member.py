import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Float, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class TeamMemberRole:
    OWNER  = "owner"
    WORKER = "worker"


class TeamMember(Base):
    __tablename__ = "team_members"

    id          : Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id : Mapped[str] = mapped_column(String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id     : Mapped[str] = mapped_column(String, ForeignKey("users.id",            ondelete="SET NULL"), nullable=True, index=True)

    # ── Identity ─────────────────────────────────────────────────────
    full_name    : Mapped[str] = mapped_column(String(255), nullable=False)
    email        : Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone_real   : Mapped[str] = mapped_column(String(20),  nullable=False)   # never exposed to users
    phone_masked : Mapped[str] = mapped_column(String(20),  nullable=True)    # Twilio proxy number
    avatar_url   : Mapped[str] = mapped_column(String(500), nullable=True)
    selfie_url   : Mapped[str] = mapped_column(String(500), nullable=True)    # verified profile photo (used for face-match check-in)
    role         : Mapped[str] = mapped_column(String(20),  default=TeamMemberRole.WORKER, nullable=False)

    # ── Auth (used only when user_id IS NULL — i.e. business workers) ─
    hashed_password : Mapped[str]      = mapped_column(String(255), nullable=True)
    last_login_at   : Mapped[datetime] = mapped_column(DateTime,    nullable=True)
    device_id       : Mapped[str]      = mapped_column(String(255), nullable=True)   # fingerprint for account-sharing detection

    # ── Live location ────────────────────────────────────────────────
    # Updated by the mobile app while the worker is en route to a job.
    # GPS pings live on a SEPARATE Redis namespace with short TTL — this
    # column is only the latest snapshot persisted to PostgreSQL.
    current_lat         : Mapped[float]    = mapped_column(Float,    nullable=True)
    current_lng         : Mapped[float]    = mapped_column(Float,    nullable=True)
    location_updated_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Status gates ─────────────────────────────────────────────────
    is_active        : Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    can_accept_jobs  : Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Internal performance (never shown to users) ──────────────────
    jobs_completed         : Mapped[int]   = mapped_column(Integer,       default=0, nullable=False)
    rating_avg             : Mapped[float] = mapped_column(Numeric(3, 2), nullable=True)
    no_show_count          : Mapped[int]   = mapped_column(Integer,       default=0, nullable=False)
    response_time_avg_min  : Mapped[float] = mapped_column(Numeric(6, 2), nullable=True)

    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    business = relationship("TradieProfile", back_populates="team_members")
    user     = relationship("User",          foreign_keys=[user_id])

    certifications = relationship(
        "TradieCertification",
        foreign_keys="TradieCertification.team_member_id",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TeamMember {self.full_name} [{self.role}] biz={self.business_id}>"