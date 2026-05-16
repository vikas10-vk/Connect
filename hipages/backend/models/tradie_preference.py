import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base


class TradiePreference(Base):
    __tablename__ = "tradie_preferences"

    id                 : Mapped[str]      = mapped_column(String,   primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id          : Mapped[str]      = mapped_column(String,   ForeignKey("tradie_profiles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Job stage preferences
    accept_high_intent : Mapped[bool]     = mapped_column(Boolean,  default=True)   # Ready to hire
    accept_planning    : Mapped[bool]     = mapped_column(Boolean,  default=True)   # Planning & budgeting

    # Notification preferences
    notify_new_lead    : Mapped[bool]     = mapped_column(Boolean,  default=True)
    notify_email       : Mapped[bool]     = mapped_column(Boolean,  default=True)
    notify_sms         : Mapped[bool]     = mapped_column(Boolean,  default=False)

    # Job type preferences
    accept_residential : Mapped[bool]     = mapped_column(Boolean,  default=True)
    accept_commercial  : Mapped[bool]     = mapped_column(Boolean,  default=True)

    # Service areas — stored as JSON string
    # Structure: [{"suburb": "Melbourne", "postcode": "3000", "state_code": "VIC"}, ...]
    # Max 20 suburbs recommended; no hard DB limit.
    service_suburbs    : Mapped[str]      = mapped_column(Text,     nullable=True)

    created_at         : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at         : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)