import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class JobEvent(Base):
    __tablename__ = "job_events"

    id:         Mapped[int]      = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id:     Mapped[str]      = mapped_column(String,     ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    # Who triggered this event
    actor_id:   Mapped[str]      = mapped_column(String,     nullable=False)          # user.id
    actor_role: Mapped[str]      = mapped_column(String(30), nullable=False)          # 'homeowner', 'tradie', 'admin', 'system'
    # What happened
    action:     Mapped[str]      = mapped_column(String(50), nullable=False)          # 'status_change', 'created', 'edited', 'photo_added', 'review_submitted', etc.
    old_value:  Mapped[dict]     = mapped_column(JSON,       nullable=True)           # e.g. {"status": "hired"}
    new_value:  Mapped[dict]     = mapped_column(JSON,       nullable=True)           # e.g. {"status": "completed"}
    # Optional context
    note:       Mapped[str]      = mapped_column(Text,       nullable=True)           # human-readable description
    ip_address: Mapped[str]      = mapped_column(String(45), nullable=True)
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime,   default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<JobEvent {self.action} job={self.job_id} by {self.actor_id}>"