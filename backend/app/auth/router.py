"""
Auth router — /api/v1/auth/...
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth import service
from app.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from app.core.responses import ok
from app.dependencies import DbDep, TokenDep

import uuid
from app.models.activity import ActivityLog

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict, status_code=201)
async def register(body: RegisterRequest, db: DbDep, request: Request):
    """Register a new NGO, Donor, or Auditor account."""
    user = await service.register_user(db, body, request)
    return ok(UserProfile.model_validate(user), message="Registration successful.")


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, db: DbDep, request: Request):
    """Authenticate and receive JWT access + refresh tokens."""
    tokens = await service.login_user(db, body, request)
    return ok(TokenResponse(**tokens))


@router.post("/refresh", response_model=dict)
async def refresh(body: RefreshRequest, db: DbDep):
    """Exchange a valid refresh token for a new token pair."""
    tokens = await service.refresh_tokens(db, body.refresh_token)
    return ok(TokenResponse(**tokens))


@router.get("/me", response_model=dict)
async def get_me(payload: TokenDep, db: DbDep):
    """Return the profile of the currently authenticated user."""
    from sqlalchemy import select
    from app.auth.models import User

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    if not user:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("User")
    return ok(UserProfile.model_validate(user))


@router.get("/login-history", response_model=dict)
async def get_login_history(payload: TokenDep, db: DbDep):
    """Retrieve recent login and authentication activity for the current user."""
    user_id = uuid.UUID(payload["sub"])
    history = await service.get_login_history(db, user_id)
    return ok(history)


@router.post("/logout", response_model=dict)
async def logout(payload: TokenDep, db: DbDep, request: Request):
    """Log out the current user session and record audit event."""
    user_id_str = payload.get("sub")
    actor_id = uuid.UUID(user_id_str) if user_id_str else None

    # Persist logout activity to database
    logout_log = ActivityLog(
        action="USER_LOGGED_OUT",
        actor_id=actor_id,
        actor_role=payload.get("role"),
        resource_type="User",
        resource_id=user_id_str,
        detail={"user_agent": request.headers.get("User-Agent")},
        success=True,
        ip_address=request.client.host if request.client else None,
    )
    db.add(logout_log)
    await db.flush()

    from app.core.logging import audit_log
    audit_log(
        action="USER_LOGGED_OUT",
        actor_id=user_id_str,
        actor_role=payload.get("role"),
        resource_type="User",
        resource_id=user_id_str,
    )
    return ok({"message": "Successfully logged out."})

