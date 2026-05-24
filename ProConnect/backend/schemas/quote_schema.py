from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class QuoteCreate(BaseModel):
    lead_id: str
    amount: float
    message: Optional[str] = None


class QuoteResponse(BaseModel):
    id: str
    lead_id: str
    tradie_id: str
    amount: float
    message: Optional[str]
    status: str
    created_at: datetime

    # Tradie info — populated by get_quotes_for_job so homeowner knows who quoted
    tradie_name: Optional[str] = None          # business_name or full_name
    tradie_business: Optional[str] = None      # business_name if set
    tradie_avatar_url: Optional[str] = None    # profile photo URL
    tradie_phone: Optional[str] = None         # contact phone (only after acceptance)
    tradie_suburb: Optional[str] = None        # tradie's service suburb

    class Config:
        from_attributes = True
