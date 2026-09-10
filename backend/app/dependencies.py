"""
Shared FastAPI dependencies injected via Depends().
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User

# ── Re-export get_db for convenience ─────────────────────────────────────────
DbDep = Annotated[AsyncSession, Depends(get_db)]

# ── Bearer token extractor ────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


async def get_current_user_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> dict:
    """
    Extract and validate the JWT from the Authorization header.
    Returns the decoded token payload dict.
    Raises UnauthorizedException if missing or invalid.
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


def require_roles(*roles: str):
    """
    Dependency factory that enforces role-based access control.

    Usage:
        @router.get("/", dependencies=[Depends(require_roles("ADMIN", "AUDITOR"))])

    Or inject the payload:
        @router.get("/")
        async def endpoint(payload: Annotated[dict, Depends(require_roles("NGO"))]):
            ...
    """

    async def _guard(
        payload: dict = Depends(get_current_user_payload),
    ) -> dict:
        user_role: str | None = payload.get("role")
        if user_role not in roles:
            raise ForbiddenException(
                f"Access denied. Required roles: {list(roles)}."
            )
        return payload

    return _guard


async def get_current_user(
    payload: TokenDep,
    db: DbDep,
) -> User:
    import uuid

    user_id = payload.get("sub")
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid token subject.")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("User")
    if not user.is_active:
        raise ForbiddenException("This account is inactive.")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
    db: DbDep = None,
) -> Optional[User]:
    """
    Extract user if valid bearer token is present; returns None if unauthenticated.
    Allows endpoints to serve public donors while recognizing logged-in users.
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        import uuid
        user_uuid = uuid.UUID(payload.get("sub"))
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
        return None
    except Exception:
        return None


OptionalUserDep = Annotated[Optional[User], Depends(get_optional_current_user)]

