"""Pydantic schemas (DTOs) for API request/response models."""
from datetime import datetime

from pydantic import BaseModel, EmailStr


# --- Auth ---

class OTPRequest(BaseModel):
    """Request an OTP code via email."""
    email: EmailStr


class OTPVerify(BaseModel):
    """Verify OTP code to get tokens."""
    email: EmailStr
    code: str


class TokenResponse(BaseModel):
    """JWT token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Refresh an access token."""
    refresh_token: str


# --- Booths ---

class BoothOut(BaseModel):
    """Booth info returned from API."""
    id: str
    booth_id: str
    name: str | None
    status: str
    last_seen: datetime | None
    cpu_percent: int | None
    camera_connected: bool
    uptime_seconds: int | None
    version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BoothRegister(BaseModel):
    """Booth self-registration via WebSocket."""
    booth_id: str
    name: str | None = None
    version: str | None = None


# --- Users ---

class UserOut(BaseModel):
    """User info."""
    id: str
    email: str
    role: str
    name: str | None
    is_active: bool
    created_at: datetime
    last_login: datetime | None

    model_config = {"from_attributes": True}
