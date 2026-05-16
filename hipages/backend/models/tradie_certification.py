import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class CertificationStatus:
    PENDING   = "pending"
    IN_REVIEW = "in_review"
    VERIFIED  = "verified"
    REJECTED  = "rejected"
    EXPIRED   = "expired"


class CertificationRejectionReason:
    INVALID_NUMBER = "invalid_number"   # number does not exist in registry
    EXPIRED        = "expired"          # licence has lapsed
    NAME_MISMATCH  = "name_mismatch"    # holder_name doesn't match registry
    WRONG_CATEGORY = "wrong_category"   # licence is for a different trade
    CANNOT_VERIFY  = "cannot_verify"    # registry unavailable, photo unclear, etc.
    OTHER          = "other"            # free-text via rejection_note


class IssuingState:
    VIC = "VIC"
    NSW = "NSW"
    QLD = "QLD"
    WA  = "WA"
    SA  = "SA"
    TAS = "TAS"
    NT  = "NT"
    ACT = "ACT"


class TradieCertification(Base):
    __tablename__ = "tradie_certifications"
    __table_args__ = (
        CheckConstraint(
            "(tradie_profile_id IS NOT NULL AND team_member_id IS NULL) OR "
            "(tradie_profile_id IS NULL AND team_member_id IS NOT NULL)",
            name="ck_tradie_certifications_owner_xor",
        ),
    )

    id : Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── XOR ownership ────────────────────────────────────────────────
    tradie_profile_id : Mapped[str] = mapped_column(
        String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    team_member_id    : Mapped[str] = mapped_column(
        String, ForeignKey("team_members.id",    ondelete="CASCADE"),
        nullable=True, index=True,
    )

    # ── Trade category this licence covers ───────────────────────────
    category_id : Mapped[str] = mapped_column(
        String, ForeignKey("categories.id"),
        nullable=False, index=True,
    )

    # ── Licence details ──────────────────────────────────────────────
    licence_number : Mapped[str] = mapped_column(String(100), nullable=False)
    issuing_state  : Mapped[str] = mapped_column(String(20),  nullable=False)
    issuing_body   : Mapped[str] = mapped_column(String(100), nullable=True)
    holder_name    : Mapped[str] = mapped_column(String(255), nullable=False)

    issued_at  : Mapped[date] = mapped_column(Date, nullable=True)
    expires_at : Mapped[date] = mapped_column(Date, nullable=True)

    # Optional photo of the licence card — speeds up admin verification
    photo_url : Mapped[str] = mapped_column(String(500), nullable=True)

    # ── Verification ─────────────────────────────────────────────────
    status             : Mapped[str]      = mapped_column(String(20), default=CertificationStatus.PENDING, nullable=False, index=True)
    rejection_reason   : Mapped[str]      = mapped_column(String(50), nullable=True)
    rejection_note     : Mapped[str]      = mapped_column(Text,       nullable=True)
    edit_request_note  : Mapped[str]      = mapped_column(Text,       nullable=True)  # tradie's reason for requesting an edit
    verified_by        : Mapped[str]      = mapped_column(String,     ForeignKey("users.id"), nullable=True)
    verified_at        : Mapped[datetime] = mapped_column(DateTime,   nullable=True)

    # ── Renewal reminder ledger ──────────────────────────────────────
    # Filled in by the daily Celery beat task that scans for expiring certs.
    # Each column records when that specific reminder email was dispatched.
    reminder_30d_sent_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_14d_sent_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_7d_sent_at  : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_1d_sent_at  : Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    tradie_profile = relationship("TradieProfile", foreign_keys=[tradie_profile_id], back_populates="certifications")
    member         = relationship("TeamMember",    foreign_keys=[team_member_id],    back_populates="certifications")
    category       = relationship("Category",      foreign_keys=[category_id])
    admin_reviewer = relationship("User",          foreign_keys=[verified_by])

    def __repr__(self):
        owner = self.team_member_id or self.tradie_profile_id
        return f"<TradieCertification {self.licence_number} [{self.issuing_state}/{self.status}] owner={owner}>"