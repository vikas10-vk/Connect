import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class Review(Base):
    __tablename__ = "reviews"

    id:           Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id:       Mapped[str] = mapped_column(String, ForeignKey("jobs.id"),            unique=True, nullable=False)
    homeowner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"),           nullable=False)
    tradie_id:    Mapped[str] = mapped_column(String, ForeignKey("tradie_profiles.id"), nullable=False)

    rating:       Mapped[int] = mapped_column(Integer, nullable=False)
    comment:      Mapped[str] = mapped_column(Text,    nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ── Moderation (admin layer — admin UI deferred) ──────────────
    status:       Mapped[str]      = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | approved | rejected
    reviewed_at:  Mapped[datetime] = mapped_column(DateTime,   nullable=True)
    reviewed_by:  Mapped[str]      = mapped_column(String,     ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # ── Admin response (admin will use later — homeowner & tradie do not) ──
    response_text: Mapped[str]      = mapped_column(Text,     nullable=True)
    responded_at:  Mapped[datetime] = mapped_column(DateTime, nullable=True)
    email_notified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # set after homeowner is emailed

    # ── Relationships ─────────────────────────────────────────────
    job       = relationship("Job", back_populates="review")
    tradie    = relationship("TradieProfile", back_populates="reviews")
    homeowner = relationship("User", foreign_keys=[homeowner_id])

    def __repr__(self):
        return f"<Review {self.rating}* job={self.job_id} status={self.status}>"