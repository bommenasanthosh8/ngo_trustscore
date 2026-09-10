"""
Auth business logic — registration, login, token refresh.
"""
from __future__ import annotations

import uuid

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.schemas import LoginRequest, RegisterRequest
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.logging import audit_log
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def _build_token_pair(user: User) -> dict[str, str]:
    extra = {"role": user.role.value, "email": user.email}
    return {
        "access_token": create_access_token(subject=str(user.id), extra=extra),
        "refresh_token": create_refresh_token(subject=str(user.id)),
        "token_type": "bearer",
    }


from datetime import datetime, timezone
from typing import Any
from fastapi import Request

from app.models.activity import ActivityLog


def _extract_client_ip(request: Request | None) -> str | None:
    if not request:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _extract_user_agent(request: Request | None) -> str | None:
    if not request:
        return None
    return request.headers.get("User-Agent")


async def register_user(db: AsyncSession, payload: RegisterRequest, request: Request | None = None) -> User:
    # Check for existing email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise ConflictException("An account with this email already exists.")

    ngo_id = None
    if payload.role == UserRole.NGO:
        from app.models.ngo import NGO
        # If organization details provided, create NGO record
        org_name = payload.organization_name or f"{payload.full_name}'s NGO"
        reg_number = payload.registration_number or f"REG-{uuid.uuid4().hex[:8].upper()}"

        # Check existing NGO
        ngo_result = await db.execute(select(NGO).where(NGO.registration_number == reg_number))
        existing_ngo = ngo_result.scalar_one_or_none()
        if existing_ngo:
            ngo_id = existing_ngo.id
        else:
            from app.models.enums import NGOVerificationStatus
            ngo = NGO(
                name=org_name,
                registration_number=reg_number,
                description=payload.description,
                address=payload.address,
                contact_phone=payload.contact_phone,
                contact_email=payload.email,
                website=payload.website,
                authorized_representative=payload.authorized_representative or payload.full_name,
                verification_status=NGOVerificationStatus.PENDING,
                is_verified=False,
            )
            db.add(ngo)
            await db.flush()
            ngo_id = ngo.id

            audit_log(
                action="NGO_CREATED",
                resource_type="NGO",
                resource_id=str(ngo.id),
                detail={
                    "name": ngo.name,
                    "registration_number": ngo.registration_number,
                    "verification_status": ngo.verification_status.value,
                },
            )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        ngo_id=ngo_id,
    )
    db.add(user)
    await db.flush()  # get the generated ID before commit

    # Persist activity log in database
    ip_addr = _extract_client_ip(request)
    user_agent = _extract_user_agent(request)
    reg_log = ActivityLog(
        action="USER_REGISTERED",
        actor_id=user.id,
        actor_role=user.role.value,
        resource_type="User",
        resource_id=str(user.id),
        detail={
            "email": user.email,
            "role": user.role.value,
            "ngo_id": str(ngo_id) if ngo_id else None,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        success=True,
        ip_address=ip_addr,
    )
    db.add(reg_log)
    await db.flush()

    audit_log(
        action="USER_REGISTERED",
        actor_id=user.id,
        actor_role=user.role.value,
        resource_type="User",
        resource_id=str(user.id),
        detail={"email": user.email, "role": user.role.value, "ngo_id": str(ngo_id) if ngo_id else None},
    )
    return user


async def login_user(db: AsyncSession, payload: LoginRequest, request: Request | None = None) -> dict[str, str]:
    ip_addr = _extract_client_ip(request)
    user_agent = _extract_user_agent(request)
    now = datetime.now(timezone.utc)

    result = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        fail_log = ActivityLog(
            action="LOGIN_FAILED",
            actor_id=user.id if user else None,
            actor_role=user.role.value if user else None,
            resource_type="User",
            resource_id=str(user.id) if user else None,
            detail={
                "email": payload.email,
                "reason": "Invalid password" if user else "User not found",
                "user_agent": user_agent,
                "attempt_time": now.isoformat(),
            },
            success=False,
            ip_address=ip_addr,
        )
        db.add(fail_log)
        await db.commit()

        audit_log(
            action="LOGIN_FAILED",
            detail={"email": payload.email},
            success=False,
        )
        raise UnauthorizedException("Invalid email or password.")

    if not user.is_active:
        deact_log = ActivityLog(
            action="LOGIN_FAILED",
            actor_id=user.id,
            actor_role=user.role.value,
            resource_type="User",
            resource_id=str(user.id),
            detail={
                "email": payload.email,
                "reason": "Account deactivated",
                "attempt_time": now.isoformat(),
            },
            success=False,
            ip_address=ip_addr,
        )
        db.add(deact_log)
        await db.commit()
        raise BadRequestException("This account has been deactivated.")

    # Record successful login details in database
    success_log = ActivityLog(
        action="LOGIN_SUCCESS",
        actor_id=user.id,
        actor_role=user.role.value,
        resource_type="User",
        resource_id=str(user.id),
        detail={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "ngo_id": str(user.ngo_id) if user.ngo_id else None,
            "user_agent": user_agent,
            "login_time": now.isoformat(),
        },
        success=True,
        ip_address=ip_addr,
    )
    db.add(success_log)
    await db.commit()

    audit_log(
        action="LOGIN_SUCCESS",
        actor_id=user.id,
        actor_role=user.role.value,
        resource_type="User",
        resource_id=str(user.id),
    )
    return _build_token_pair(user)


async def get_login_history(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent login / session activity for a user."""
    result = await db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.actor_id == user_id,
            ActivityLog.action.in_(["LOGIN_SUCCESS", "LOGIN_FAILED", "USER_LOGGED_OUT"]),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "actor_role": log.actor_role,
            "ip_address": log.ip_address,
            "success": log.success,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "detail": log.detail,
        }
        for log in logs
    ]


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict[str, str]:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise UnauthorizedException("Refresh token is invalid or has expired.")

    if payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid token type.")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise UnauthorizedException("User not found or deactivated.")

    return _build_token_pair(user)

