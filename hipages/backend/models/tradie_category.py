"""
backend/models/tradie_category.py

UPDATED — adds is_primary flag.

UNCHANGED: tradie_id, category_id, relationships.

NEW FIELD: is_primary
  A tradie can service multiple categories. is_primary = True marks the
  one shown as their headline trade on their public profile and in search
  results. Exactly one row per tradie_id should have is_primary = True
  (enforced in the router, not at DB level — a partial unique index would
  require a function-based index in Postgres which adds complexity for
  minimal gain at this scale).

NOTE: category_id should always point to a level-1 Category row (the
  trade category). Tradies are not registered per-subcategory — their
  licence covers the whole trade. The level-2 and level-3 categories exist
  for job classification and service questions only.
"""
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class TradieCategory(Base):
    __tablename__ = "tradie_categories"

    # ── Existing fields (UNCHANGED) ────────────────────────────────
    tradie_id:   Mapped[str] = mapped_column(String, ForeignKey("tradie_profiles.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[str] = mapped_column(String, ForeignKey("categories.id",      ondelete="CASCADE"), primary_key=True)

    # ── NEW ────────────────────────────────────────────────────────
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True for the tradie's headline trade shown on their public profile.

    # ── Relationships (UNCHANGED) ──────────────────────────────────
    tradie   = relationship("TradieProfile", back_populates="tradie_categories")
    category = relationship("Category")