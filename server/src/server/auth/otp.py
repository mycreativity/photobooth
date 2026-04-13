"""OTP generation, verification, and magic link tokens."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.db import OTPCode

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5


def generate_otp() -> tuple[str, str]:
    """Generate a 6-digit OTP code and a magic link token.

    Returns:
        (code, magic_token)
    """
    code = "".join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))
    magic_token = secrets.token_urlsafe(48)
    return code, magic_token


async def create_otp(db: AsyncSession, email: str) -> tuple[str, str]:
    """Create and store an OTP for the given email.

    Invalidates any previous unused OTPs for the same email.

    Returns:
        (code, magic_token)
    """
    # Invalidate previous codes
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.email == email,
            OTPCode.used == False,  # noqa: E712
        )
    )
    for old in result.scalars():
        old.used = True

    code, magic_token = generate_otp()
    otp = OTPCode(
        email=email,
        code=code,
        magic_token=magic_token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(otp)
    await db.commit()

    logger.info("OTP created for %s (code=%s)", email, code)
    return code, magic_token


async def verify_otp_code(db: AsyncSession, email: str, code: str) -> bool:
    """Verify a 6-digit OTP code.

    Returns True if valid, False otherwise. Marks as used on success.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.email == email,
            OTPCode.code == code,
            OTPCode.used == False,  # noqa: E712
            OTPCode.expires_at > now,
        )
    )
    otp = result.scalar_one_or_none()
    if not otp:
        return False

    otp.used = True
    await db.commit()
    logger.info("OTP verified for %s", email)
    return True


async def verify_magic_token(db: AsyncSession, token: str) -> str | None:
    """Verify a magic link token.

    Returns the email if valid, None otherwise. Marks as used on success.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.magic_token == token,
            OTPCode.used == False,  # noqa: E712
            OTPCode.expires_at > now,
        )
    )
    otp = result.scalar_one_or_none()
    if not otp:
        return None

    otp.used = True
    await db.commit()
    logger.info("Magic link verified for %s", otp.email)
    return otp.email
