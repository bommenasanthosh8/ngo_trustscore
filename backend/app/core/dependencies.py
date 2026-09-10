"""
FastAPI shared dependencies.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token

# ── Re-export for convenience ─────────────────────────────────────────────────
DbDep = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> dict:
    """
    Extract and validate the JWT from the Authorization header.
    Returns the decoded token payload dict.
    """
    if credentials is None:
        raise UnauthorizedException("Authentication credentials were not provided.")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise UnauthorizedException("Token is invalid or has expired.")
    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type.")
    return payload


TokenDep = Annotated[dict, Depends(get_current_user_payload)]


async def get_current_user(
    payload: TokenDep,
    db: DbDep,
):
    """Fetch the active User ORM instance for the authenticated token."""
    from sqlalchemy import select
    from app.models.user import User

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token subject.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid user ID format in token.")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User no longer exists.")
    if not user.is_active:
        raise ForbiddenException("User account is inactive.")

    return user


CurrentUserDep = Annotated[Any, Depends(get_current_user)]


def require_roles(*roles: str):
    """
    RBAC dependency factory.

    Usage:
        @router.post("/", dependencies=[Depends(require_roles("NGO", "ADMIN"))])
        async def create(...):
            ...

        # Or inject the payload:
        async def create(payload = Depends(require_roles("NGO"))):
            ngo_user_id = uuid.UUID(payload["sub"])
    """
    async def _guard(
        payload: dict = Depends(get_current_user_payload),
    ) -> dict:
        user_role: str | None = payload.get("role")
        if user_role not in roles:
            raise ForbiddenException(
                f"Access denied. Allowed roles: {list(roles)}."
            )
        return payload

    return _guard

