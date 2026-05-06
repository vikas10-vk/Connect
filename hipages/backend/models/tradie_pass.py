import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Boolean, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base


class TradiePass(Base):
    __tablename__ = "tradie_pass"

    id              : Mapped[str]           = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tradie_id       : Mapped[str]           = mapped_column(String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # ABN verification
    abn             : Mapped[str | None]    = mapped_column(String(20), nullable=True)
    abn_verified    : Mapped[bool]          = mapped_column(Boolean, default=False)
    abn_name        : Mapped[str | None]    = mapped_column(String(200), nullable=True)
    abn_status      : Mapped[str | None]    = mapped_column(String(50), nullable=True)
    abn_verified_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Licence
    licence_number  : Mapped[str | None]    = mapped_column(String(100), nullable=True)
    licence_type    : Mapped[str | None]    = mapped_column(String(100), nullable=True)
    licence_state   : Mapped[str | None]    = mapped_column(String(10), nullable=True)
    licence_expiry  : Mapped[date | None]   = mapped_column(Date, nullable=True)
    licence_doc_url : Mapped[str | None]    = mapped_column(String(500), nullable=True)
    licence_verified: Mapped[bool]          = mapped_column(Boolean, default=False)

    # Public Liability Insurance
    pli_insurer     : Mapped[str | None]    = mapped_column(String(200), nullable=True)
    pli_amount_m    : Mapped[float | None]  = mapped_column(Float, nullable=True)   # in millions
    pli_expiry      : Mapped[date | None]   = mapped_column(Date, nullable=True)
    pli_doc_url     : Mapped[str | None]    = mapped_column(String(500), nullable=True)
    pli_verified    : Mapped[bool]          = mapped_column(Boolean, default=False)

    # Workers Compensation
    wc_insurer      : Mapped[str | None]    = mapped_column(String(200), nullable=True)
    wc_expiry       : Mapped[date | None]   = mapped_column(Date, nullable=True)
    wc_doc_url      : Mapped[str | None]    = mapped_column(String(500), nullable=True)
    wc_verified     : Mapped[bool]          = mapped_column(Boolean, default=False)

    # White Card
    white_card_number: Mapped[str | None]   = mapped_column(String(100), nullable=True)
    white_card_verified: Mapped[bool]       = mapped_column(Boolean, default=False)

    # SWMS
    swms_uploaded   : Mapped[bool]          = mapped_column(Boolean, default=False)
    swms_doc_url    : Mapped[str | None]    = mapped_column(String(500), nullable=True)
    swms_updated_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Calculated score and badge
    pass_score      : Mapped[int]           = mapped_column(Integer, default=0)
    badge_level     : Mapped[str]           = mapped_column(String(20), default="bronze")

    created_at      : Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    updated_at      : Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TradiePass {self.tradie_id} score={self.pass_score}>"