# =============================================================================
# schemas/user_schema.py — Request and response schemas
# Tradie Platform
# =============================================================================

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class RoleEnum(str, Enum):
    homeowner = "homeowner"
    tradie    = "tradie"


# =============================================================================
# Auth request schemas
# =============================================================================

class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str = Field(
        min_length=8,
        max_length=72,
        # max_length=72 is not arbitrary — bcrypt silently truncates at 72 bytes.
        # A 200-char password is identical to its first 72 chars.
        # Without this limit, a user setting a 200-char password believes they have
        # a stronger credential than they actually do.
        # Also prevents DoS: an attacker sending 1MB passwords causes bcrypt CPU spikes.
    )
    full_name: str = Field(min_length=1, max_length=255)
    phone:     Optional[str] = None
    role:      RoleEnum

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Enforce minimum password complexity.

        Requirements:
        - At least 8 characters (enforced by Field min_length)
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit

        We deliberately do NOT require special characters — they reduce
        the character space users draw from (they just add "!" at the end)
        and are worse for usability than length requirements.
        NIST SP 800-63B agrees: length matters more than character classes.
        """
        errors = []

        if not any(c.isupper() for c in v):
            errors.append("at least one uppercase letter")

        if not any(c.islower() for c in v):
            errors.append("at least one lowercase letter")

        if not any(c.isdigit() for c in v):
            errors.append("at least one number")

        # Reject the most common passwords regardless of complexity.
        COMMON_PASSWORDS = {
            "password1", "Password1", "password123", "Password123",
            "12345678", "qwerty123", "Qwerty123", "letmein1", "welcome1",
        }
        if v.lower() in {p.lower() for p in COMMON_PASSWORDS}:
            errors.append("cannot be a commonly used password")

        if errors:
            raise ValueError(
                f"Password must contain {', '.join(errors)}"
            )

        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase at schema level."""
        return v.lower().strip()


class LoginRequest(BaseModel):
    email:         EmailStr
    password:      str = Field(max_length=72)  # Prevent DoS on login too
    expected_role: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="The refresh token received at login.")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(description="The refresh token to revoke.")


# =============================================================================
# Auth response schemas
# =============================================================================

class TokenResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    expires_in:    int = Field(description="Access token lifetime in seconds.")
    refresh_token: Optional[str] = None


class RefreshResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int


# =============================================================================
# User response schema
# =============================================================================

class UserResponse(BaseModel):
    id:             str
    email:          str
    full_name:      str
    phone:          Optional[str] = None
    role:           str
    is_active:      bool
    is_verified:    bool
    email_verified: bool
    created_at:     datetime
    updated_at:     datetime

    model_config = {"from_attributes": True}