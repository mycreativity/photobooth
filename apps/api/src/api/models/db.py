"""SQLAlchemy models for the photobooth server."""
import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, String, Text, Boolean, Integer, func
from sqlalchemy.orm import DeclarativeBase


def generate_short_uid() -> str:
    """Generate an 8-character lowercase hex UID for QR codes."""
    return secrets.token_hex(4)


def generate_api_key() -> str:
    """Generate a 32-character hex API key for booth auth."""
    return secrets.token_hex(16)


def hash_api_key(api_key: str) -> str:
    """Hash an API key with SHA-256 for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """Admin and public users — authenticated via OTP email."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(String(20), nullable=False, default="user")  # admin | user
    name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)


class OTPCode(Base):
    """One-time passwords for email-based login."""
    __tablename__ = "otp_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    magic_token = Column(String(64), nullable=True, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class RefreshToken(Base):
    """Refresh tokens for session continuity."""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Event(Base):
    """Events — group photobooth sessions, with short UID for QR codes."""
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uid = Column(String(8), unique=True, nullable=False, index=True, default=generate_short_uid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    date = Column(DateTime, nullable=True)       # Start date
    end_date = Column(DateTime, nullable=True)   # End date
    is_active = Column(Boolean, default=True)
    # Photo card customization
    background_image = Column(String(500), nullable=True)  # filename in /data/backgrounds/
    branding_text = Column(Text, nullable=True)             # Markdown text for branding strip
    display_date = Column(String(100), nullable=True)       # e.g. "Woensdag 15 April 2026"
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Booth(Base):
    """Registered photobooth devices."""
    __tablename__ = "booths"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booth_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key_hash = Column(String(64), nullable=True)  # SHA-256 hash of API key
    event_id = Column(String(36), nullable=True)  # Active event for this booth
    status = Column(String(20), default="offline")  # online | offline | error
    last_seen = Column(DateTime, nullable=True)
    cpu_percent = Column(Integer, nullable=True)
    camera_connected = Column(Boolean, default=False)
    uptime_seconds = Column(Integer, nullable=True)
    version = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Session(Base):
    """Photo sessions — one per capture flow on the booth."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), nullable=True, index=True)
    booth_id = Column(String(100), nullable=True)
    photo_count = Column(Integer, default=0)
    layout = Column(String(50), nullable=True)
    filter_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Photo(Base):
    """Photos uploaded from booths."""
    __tablename__ = "photos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=True, index=True)
    event_id = Column(String(36), nullable=True, index=True)
    booth_id = Column(String(100), nullable=True)
    seq = Column(Integer, default=1)
    variant = Column(String(50), default="final")  # original | final | print
    filename = Column(String(500), nullable=False)  # relative path on server
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
