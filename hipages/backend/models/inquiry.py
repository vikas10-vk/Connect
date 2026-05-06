import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class Inquiry(Base):
    __tablename__ = "inquiries"

    id:         Mapped[str] = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id:  Mapped[str] = mapped_column(String,      ForeignKey("tradie_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id:  Mapped[str] = mapped_column(String,      ForeignKey("users.id",           ondelete="CASCADE"), nullable=False)
    name:       Mapped[str] = mapped_column(String(255), nullable=False)
    email:      Mapped[str] = mapped_column(String(255), nullable=False)
    phone:      Mapped[str] = mapped_column(String(20),  nullable=True)
    message:    Mapped[str] = mapped_column(Text,        nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────────
    tradie = relationship("TradieProfile")
    sender = relationship("User", foreign_keys=[sender_id])

    def __repr__(self):
        return f"<Inquiry from {self.name} to tradie {self.tradie_id}>"