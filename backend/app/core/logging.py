"""
Structured audit logging via structlog.
All important platform actions (auth, evidence submission, verification, audit decisions)
MUST call audit_log() so there is a complete traceable record.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# ── stdlib logging → structlog bridge ────────────────────────────────────────
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if True else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


logger = structlog.get_logger("ngo_platform")


def audit_log(
    *,
    action: str,
    actor_id: str | int | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    """
    Emit a structured audit log entry.

    This is intentionally a synchronous function so it can be called from
    both sync and async contexts. For database-persisted audit logs, use
    the AuditLog ORM model instead (or in addition).
    """
    logger.info(
        "AUDIT",
        action=action,
        actor_id=str(actor_id) if actor_id is not None else None,
        actor_role=actor_role,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail,
        success=success,
    )
