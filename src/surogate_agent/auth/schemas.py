"""Pydantic schemas for the auth module."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")
_VALID_ROLES = {"developer", "user"}


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3–64 characters and contain only letters, "
                "digits, underscores, or hyphens."
            )
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
