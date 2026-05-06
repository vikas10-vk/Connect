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

    class Config:
        from_attributes = True