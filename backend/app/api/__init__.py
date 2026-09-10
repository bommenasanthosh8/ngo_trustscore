"""API router package."""
from fastapi import APIRouter
from app.auth.router import router as auth_router
from app.projects.router import router as projects_router
from app.evidence.router import router as evidence_router
from app.verification.router import router as verification_router
from app.audit.router import router as audit_router
from app.scores.router import router as scores_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(scores_router)

__all__ = ["api_v1_router"]
