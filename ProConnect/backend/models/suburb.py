from sqlalchemy import Column, Index, Integer, String

from db.session import Base


class Suburb(Base):
    __tablename__ = "suburbs"

    id          = Column(Integer, primary_key=True, index=True)
    suburb      = Column(String(100), nullable=False)
    postcode    = Column(String(10),  nullable=False)   # VARCHAR — NT codes start with 0
    state       = Column(String(50),  nullable=False)
    state_code  = Column(String(5),   nullable=False)

    __table_args__ = (
        # Fast prefix search on suburb name (used by autocomplete)
        Index("ix_suburbs_suburb_lower", "suburb"),
        # Postcode lookup (tradie radius matching)
        Index("ix_suburbs_postcode", "postcode"),
        # State filter
        Index("ix_suburbs_state_code", "state_code"),
    )

    def to_dict(self):
        return {
            "id":         self.id,
            "suburb":     self.suburb,
            "postcode":   self.postcode,
            "state":      self.state,
            "state_code": self.state_code,
            "label":      f"{self.suburb}, {self.state_code} {self.postcode}",
        }
