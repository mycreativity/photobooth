"""SQLAlchemy models for the photobooth server."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, String, Text, Boolean, Integer, func
from sqlalchemy.orm import DeclarativeBase


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


class Booth(Base):
    """Registered photobooth devices."""
    __tablename__ = "booths"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booth_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key = Column(String(128), nullable=True)
    status = Column(String(20), default="offline")  # online | offline | error
    last_seen = Column(DateTime, nullable=True)
    cpu_percent = Column(Integer, nullable=True)
    camera_connected = Column(Boolean, default=False)
    uptime_seconds = Column(Integer, nullable=True)
    version = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
