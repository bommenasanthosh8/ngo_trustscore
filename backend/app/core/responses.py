"""
Shared FastAPI response envelopes.

All API endpoints MUST return one of these shapes so that the frontend
can reliably parse success / error payloads.
"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard success response."""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    success: bool = True
    data: list[T] = []
    message: Optional[str] = None
    meta: PaginationMeta = None  # type: ignore[assignment]


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class APIErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    details: Optional[list[ErrorDetail]] = None


def ok(data: Any = None, message: str | None = None) -> dict:
    return APIResponse(success=True, data=data, message=message).model_dump(
        exclude_none=True
    )


def err(error: str, details: list[dict] | None = None) -> dict:
    return APIErrorResponse(
        success=False,
        error=error,
        details=[ErrorDetail(**d) for d in details] if details else None,
    ).model_dump(exclude_none=True)
