from typing import Any, Optional

from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthSignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    full_name: str = ""


class PasswordResetRequest(BaseModel):
    email: str


class AuthUrlResponse(BaseModel):
    url: str


class UserMeResponse(BaseModel):
    id: str
    email: Optional[str] = None
    role: str
    tier: str = "self"
    created_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
