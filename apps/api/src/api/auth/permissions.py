"""Role-based access control dependencies for FastAPI."""
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.oauth2 import decode_token

logger = logging.getLogger(__name__)

security = HTTPBearer()


class CurrentUser:
    """Decoded JWT payload — injected via Depends()."""
    def __init__(self, user_id: str, email: str, role: str):
        self.user_id = user_id
        self.email = email
        self.role = role

    def __repr__(self) -> str:
        return f"CurrentUser({self.email}, role={self.role})"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    """Validate Bearer token and return current user."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
    )


def require_role(*allowed_roles: str):
    """FastAPI dependency: require one of the given roles.

    Usage::

        @router.get("/admin-only")
        async def admin_only(user = Depends(require_role("admin"))):
            ...
    """
    async def _check(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized. Required: {allowed_roles}",
            )
        return user
    return _check
