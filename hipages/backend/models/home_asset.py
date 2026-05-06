import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class HomeAsset(Base):
    __tablename__ = "home_assets"

    id               : Mapped[str]      = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    homeowner_id     : Mapped[str]      = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type       : Mapped[str]      = mapped_column(String(100), nullable=False)
    brand_name       : Mapped[str]      = mapped_column(String(200), nullable=False)
    installation_date: Mapped[date]     = mapped_column(Date, nullable=False)
    warranty_months  : Mapped[int]      = mapped_column(Integer, default=12)
    tradie_name      : Mapped[str]      = mapped_column(String(200), nullable=True)
    job_id           : Mapped[str]      = mapped_column(String, nullable=True)
    invoice_number   : Mapped[str]      = mapped_column(String(100), nullable=True)
    notes            : Mapped[str]      = mapped_column(String(500), nullable=True)
    expected_lifespan: Mapped[int]      = mapped_column(Integer, default=120)  # in months
    created_at       : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at       : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HomeAsset {self.asset_type} - {self.brand_name}>"