import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class Lead(Base):
    __tablename__ = "leads"

    id:              Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id:          Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    tradie_id:       Mapped[str] = mapped_column(String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=1)
    status:          Mapped[str] = mapped_column(String(20), default="sent", nullable=False)
    sent_at:         Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job    = relationship("Job", back_populates="leads")
    tradie = relationship("TradieProfile")

    def __repr__(self):
        return f"<Lead job={self.job_id} tradie={self.tradie_id}>"