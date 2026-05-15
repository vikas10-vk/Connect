import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Text, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class InsuranceType:
    PUBLIC_LIABILITY        = "public_liability"
    WORKERS_COMPENSATION    = "workers_compensation"
    PROFESSIONAL_INDEMNITY  = "professional_indemnity"


class InsuranceStatus:
    PENDING   = "pending"
    IN_REVIEW = "in_review"
    VERIFIED  = "verified"
    REJECTED  = "rejected"
    EXPIRED   = "expired"


class InsuranceRejectionReason:
    INVALID_NUMBER     = "invalid_number"      # policy doesn't exist with this insurer
    EXPIRED            = "expired"             # policy has lapsed
    NAME_MISMATCH      = "name_mismatch"       # policy holder doesn't match the business
    INSUFFICIENT_COVER = "insufficient_cover"  # coverage below category minimum
    CANNOT_VERIFY      = "cannot_verify"       # insurer unreachable, document unclear, etc.
    OTHER              = "other"


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id : Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    tradie_profile_id : Mapped[str] = mapped_column(
        String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # ── Policy details ───────────────────────────────────────────────
    insurance_type        : Mapped[str] = mapped_column(String(30),  default=InsuranceType.PUBLIC_LIABILITY, nullable=False)
    insurer_name          : Mapped[str] = mapped_column(String(255), nullable=False)
    policy_number         : Mapped[str] = mapped_column(String(100), nullable=False)
    coverage_amount_cents : Mapped[int] = mapped_column(BigInteger,  nullable=False)
    # Coverage stored in cents — never floats. AU public liability is
    # commonly $20,000,000.00 → 2_000_000_000 cents.
    holder_name           : Mapped[str] = mapped_column(String(255), nullable=False)

    issued_at  : Mapped[date] = mapped_column(Date, nullable=True)
    expires_at : Mapped[date] = mapped_column(Date, nullable=False)

    # Optional certificate-of-currency upload — speeds up admin verification
    document_url : Mapped[str] = mapped_column(String(500), nullable=True)

    # ── Verification ─────────────────────────────────────────────────
    status             : Mapped[str]      = mapped_column(String(20), default=InsuranceStatus.PENDING, nullable=False, index=True)
    rejection_reason   : Mapped[str]      = mapped_column(String(50), nullable=True)
    rejection_note     : Mapped[str]      = mapped_column(Text,       nullable=True)
    edit_request_note  : Mapped[str]      = mapped_column(Text,       nullable=True)  # tradie's reason for requesting an edit
    verified_by        : Mapped[str]      = mapped_column(String,     ForeignKey("users.id"), nullable=True)
    verified_at        : Mapped[datetime] = mapped_column(DateTime,   nullable=True)

    # ── Renewal reminder ledger ──────────────────────────────────────
    reminder_30d_sent_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_14d_sent_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_7d_sent_at  : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reminder_1d_sent_at  : Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    tradie_profile = relationship("TradieProfile", back_populates="insurance_policies")
    admin_reviewer = relationship("User",          foreign_keys=[verified_by])

    def __repr__(self):
        return f"<InsurancePolicy {self.policy_number} [{self.insurance_type}/{self.status}]>"