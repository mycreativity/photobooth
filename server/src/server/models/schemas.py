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


# --- Events ---

class EventCreate(BaseModel):
    """Create a new event."""
    name: str
    description: str | None = None
    date: datetime | None = None
    end_date: datetime | None = None
    branding_text: str | None = None
    display_date: str | None = None


class EventUpdate(BaseModel):
    """Partial update of an event."""
    name: str | None = None
    description: str | None = None
    date: datetime | None = None
    end_date: datetime | None = None
    is_active: bool | None = None
    branding_text: str | None = None
    display_date: str | None = None


class EventOut(BaseModel):
    """Event info returned from API."""
    id: str
    uid: str
    name: str
    description: str | None
    date: datetime | None
    end_date: datetime | None = None
    is_active: bool
    background_image: str | None = None
    branding_text: str | None = None
    display_date: str | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# --- Booths ---

class BoothCreate(BaseModel):
    """Register a new booth (admin chooses booth_id)."""
    booth_id: str
    name: str | None = None


class BoothUpdate(BaseModel):
    """Update booth info."""
    name: str | None = None
    event_id: str | None = None


class BoothOut(BaseModel):
    """Booth info returned from API."""
    id: str
    booth_id: str
    name: str | None
    event_id: str | None
    status: str
    last_seen: datetime | None
    cpu_percent: int | None
    camera_connected: bool
    uptime_seconds: int | None
    version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BoothCreatedOut(BaseModel):
    """Response after creating a booth — includes plaintext API key (shown only once)."""
    id: str
    booth_id: str
    name: str | None
    api_key: str  # plaintext — only returned at creation/regeneration


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

