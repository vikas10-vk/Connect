
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: str | None = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    parent_id: str | None

    class Config:
        from_attributes = True
