import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class EarningsRecord(Base):
    __tablename__ = "earnings_records"

    id           : Mapped[str]      = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id    : Mapped[str]      = mapped_column(String,      ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id       : Mapped[str]      = mapped_column(String,      ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    # Date fields for fast summing
    month        : Mapped[int]      = mapped_column(Integer,     nullable=False, index=True)
    year         : Mapped[int]      = mapped_column(Integer,     nullable=False, index=True)

    # Amount fields
    gross_amount : Mapped[float]    = mapped_column(Float,       nullable=False)
    platform_fee : Mapped[float]    = mapped_column(Float,       default=0.0)
    gst_amount   : Mapped[float]    = mapped_column(Float,       default=0.0)
    tax_buffer   : Mapped[float]    = mapped_column(Float,       default=0.0)
    net_estimate : Mapped[float]    = mapped_column(Float,       nullable=False)

    created_at   : Mapped[datetime] = mapped_column(DateTime,    default=datetime.utcnow)

    # Relationships
    tradie = relationship("TradieProfile")
    job    = relationship("Job")

    def __repr__(self):
        return f"<EarningsRecord tradie={self.tradie_id} amount={self.gross_amount}>"
