"""OAuth2 token creation and validation."""
import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from server.config import settings

logger = logging.getLogger(__name__)

# Re-export for convenience
ALGORITHM = settings.jwt_algorithm
SECRET = settings.jwt_secret


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=15))

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=7))

    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token.

    Returns the payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug("Token decode failed: %s", e)
        return None
