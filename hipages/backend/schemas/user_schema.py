from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional, Literal

class UserRole(str, Enum):
    HOMEOWNER = "homeowner"
    TRADIE    = "tradie"

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    password: str
    role: UserRole

class LoginRequest(BaseModel):
    email:         EmailStr
    password:      str
    expected_role: Optional[Literal["homeowner", "tradie"]] = None  # frontend enforces which login page

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_verified: bool
    email_verified: bool


    class Config:
        from_attributes = True