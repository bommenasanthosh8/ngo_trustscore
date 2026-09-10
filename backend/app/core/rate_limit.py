"""
In-memory Sliding Window Rate Limiting Middleware.

Provides high-performance, self-contained rate limiting without requiring
external dependencies like Redis. Protects sensitive authentication endpoints
from brute-force/credential-stuffing attacks and shields APIs from abusive traffic.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.responses import err


class SlidingWindowRateLimiter:
    """Sliding-window request tracker per client IP and route category."""

    def __init__(self) -> None:
        # Map: category -> (client_ip -> list of timestamps)
        self._history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    def is_allowed(
        self,
        category: str,
        client_ip: str,
        limit: int,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under sliding window.
        Returns: (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds
        records = self._history[category][client_ip]

        # Evict timestamps older than the window
        valid_records = [t for t in records if t > window_start]
        self._history[category][client_ip] = valid_records

        if len(valid_records) >= limit:
            oldest = valid_records[0]
            retry_after = max(1, int(oldest + window_seconds - now))
            return False, 0, retry_after

        # Record this request
        valid_records.append(now)
        remaining = max(0, limit - len(valid_records))
        return True, remaining, 0

    def reset(self) -> None:
        """Clear all rate limit records (useful for automated testing)."""
        self._history.clear()


limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying tiered rate limits:
    - Sensitive auth routes (/auth/login, /auth/register): 20 req/minute
    - General API routes: 300 req/minute
    - Health checks (/health, /): Exempt
    """

    def __init__(self, app, enabled: bool = True) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        # In testing environment, bypass unless test explicitly tests rate limiting
        if self.settings.APP_ENV == "testing" and request.headers.get("X-Test-RateLimit-Check") != "true":
            return await call_next(request)

        # Allow disabling via env or test toggle
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Exempt health & root endpoints
        if path in ("/health", "/", "/api/v1/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Determine client identifier (Forwarded-For or client host)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # Tier 1: Sensitive authentication endpoints (Anti-brute force)
        if path in ("/api/v1/auth/login", "/auth/login", "/api/v1/auth/register", "/auth/register"):
            limit = 20
            window = 60
            category = "auth_sensitive"
        else:
            # Tier 2: General API operations
            limit = 300
            window = 60
            category = "api_general"

        allowed, remaining, retry_after = limiter.is_allowed(
            category=category,
            client_ip=client_ip,
            limit=limit,
            window_seconds=window,
        )

        if not allowed:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=err(f"Rate limit exceeded. Try again in {retry_after} seconds."),
                headers={"Retry-After": str(retry_after)},
            )
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
