"""
NGO Transparency Platform — FastAPI application entrypoint.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.router import router as admin_router
from app.audit.router import router as audit_router, audit_cases_router
from app.auth.router import router as auth_router
from fastapi.exceptions import RequestValidationError
from app.config import get_settings
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.responses import ok
from app.evidence.router import router as evidence_router
from app.ngos.router import router as ngos_router
from app.projects.router import router as projects_router
from app.public.router import router as public_router
from app.risk.router import router as risk_router
from app.scores.router import router as scores_router
from app.verification.router import router as verification_router
from app.demo.router import router as demo_router
from app.donations.router import router as donations_router

settings = get_settings()



# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.core.logging import logger
    logger.info("Starting NGO Transparency Platform", env=settings.APP_ENV)
    yield
    # Shutdown
    logger.info("Shutting down NGO Transparency Platform")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Evidence-Based NGO Fund Utilization Transparency & Trust Platform. "
        "Backend API documentation."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

from app.core.rate_limit import RateLimitMiddleware

# ── CORS ──────────────────────────────────────────────────────────────────────
cors_origins = settings.cors_origins_list
# Disallow wildcard origin with credentials for browser security
allow_creds = True
if "*" in cors_origins:
    allow_creds = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware, enabled=True)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = settings.API_V1_PREFIX

app.include_router(auth_router, prefix=PREFIX)
app.include_router(ngos_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(projects_router, prefix=PREFIX)
app.include_router(evidence_router, prefix=PREFIX)
app.include_router(verification_router, prefix=PREFIX)
app.include_router(risk_router, prefix=PREFIX)
app.include_router(audit_router, prefix=PREFIX)
app.include_router(audit_cases_router, prefix=PREFIX)
app.include_router(scores_router, prefix=PREFIX)
app.include_router(public_router, prefix=PREFIX)
app.include_router(demo_router, prefix=PREFIX)
app.include_router(donations_router, prefix=PREFIX)

# Direct root paths (e.g. /auth/register, /ngos, /admin/ngos/pending, /projects)
app.include_router(auth_router)
app.include_router(ngos_router)
app.include_router(admin_router)
app.include_router(projects_router)
app.include_router(evidence_router)
app.include_router(verification_router)
app.include_router(risk_router)
app.include_router(audit_router)
app.include_router(audit_cases_router)
app.include_router(scores_router)
app.include_router(public_router)
app.include_router(demo_router)
app.include_router(donations_router)



# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return ok({"status": "ok", "version": "0.1.0"})


@app.get("/", tags=["Root"])
async def root():
    return ok({"message": f"Welcome to the {settings.APP_NAME} API. Visit /docs for documentation."})
