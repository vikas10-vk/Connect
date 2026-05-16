import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class Quote(Base):
    __tablename__ = "quotes"

    id:         Mapped[str]   = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id:    Mapped[str]   = mapped_column(String, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    tradie_id:  Mapped[str]   = mapped_column(String, ForeignKey("tradie_profiles.id"), nullable=False)
    amount:     Mapped[float] = mapped_column(Float, nullable=False)
    message:    Mapped[str]   = mapped_column(Text, nullable=True)
    status:     Mapped[str]   = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead   = relationship("Lead")
    tradie = relationship("TradieProfile")

    def __repr__(self):
        return f"<Quote ${self.amount} [{self.status}]>"