"""Auth API endpoints — OTP login, token refresh, magic link."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.oauth2 import create_access_token, create_refresh_token, decode_token
from server.auth.otp import create_otp, verify_magic_token, verify_otp_code
from server.config import settings
from server.database import get_db
from server.email.sender import send_otp_email
from server.models.db import RefreshToken, User
from server.models.schemas import OTPRequest, OTPVerify, RefreshRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _create_token_response(user: User) -> dict:
    """Build access + refresh token pair for a user."""
    access = create_access_token(
        user_id=user.id, email=user.email, role=user.role,
        expires_delta=timedelta(minutes=15),
    )
    refresh = create_refresh_token(
        user_id=user.id,
        expires_delta=timedelta(days=7),
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 15 * 60,
    }


@router.post("/otp/request")
async def request_otp(body: OTPRequest, db: AsyncSession = Depends(get_db)):
    """Send OTP code + magic link to email.

    Works for both admin and public users. If the email doesn't exist
    in the users table, a new user account is created with role=user.
    """
    email = body.email.lower().strip()

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create public user
        user = User(email=email, role="user")
        db.add(user)
        await db.commit()
        logger.info("Auto-created user: %s (role=user)", email)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Generate OTP
    code, magic_token = await create_otp(db, email)

    # Build magic link
    magic_link = f"{settings.admin_url}/auth/magic/{magic_token}"

    # Send email (non-blocking — if SMTP is not configured, log code for development)
    sent = send_otp_email(email, code, magic_link)
    if not sent:
        logger.warning("Email not sent — OTP code for %s: %s (dev mode)", email, code)

    return {"message": "OTP sent", "email": email}


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp(body: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify OTP code and return JWT tokens."""
    email = body.email.lower().strip()

    valid = await verify_otp_code(db, email, body.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP code",
        )

    # Get user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return _create_token_response(user)


@router.get("/otp/magic/{token}")
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)):
    """Verify magic link token and return JWT tokens.

    The frontend redirects the user to this endpoint after
    clicking the magic link in the email.
    """
    email = await verify_magic_token(db, token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return _create_token_response(user)


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for new access + refresh tokens."""
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return _create_token_response(user)


from server.auth.permissions import CurrentUser, get_current_user


@router.get("/me")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info from token."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "email": db_user.email,
        "role": db_user.role,
        "name": db_user.name,
    }
