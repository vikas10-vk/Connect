from pydantic import BaseModel
from typing import Optional, List

class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: Optional[str] = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    parent_id: Optional[str]

    class Config:
        from_attributes = True