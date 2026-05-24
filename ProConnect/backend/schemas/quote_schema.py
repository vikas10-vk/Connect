from datetime import datetime

from pydantic import BaseModel


class QuoteCreate(BaseModel):
    lead_id: str
    amount: float
    message: str | None = None


class QuoteResponse(BaseModel):
    id: str
    lead_id: str
    tradie_id: str
    amount: float
    message: str | None
    status: str
    created_at: datetime

    # Tradie info — populated by get_quotes_for_job so homeowner knows who quoted
    tradie_name: str | None = None          # business_name or full_name
    tradie_business: str | None = None      # business_name if set
    tradie_avatar_url: str | None = None    # profile photo URL
    tradie_phone: str | None = None         # contact phone (only after acceptance)
    tradie_suburb: str | None = None        # tradie's service suburb

    class Config:
        from_attributes = True
