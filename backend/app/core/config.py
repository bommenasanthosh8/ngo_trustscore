"""
Application settings — single source of truth for all configuration.
Reads from .env file via pydantic-settings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    APP_NAME: str = "NGO Transparency Platform"
    APP_ENV: str = "development"           # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ───────────────────────────────────────────────────
    DATABASE_URL: str                      # postgresql+asyncpg://...
    SYNC_DATABASE_URL: str                 # postgresql+psycopg://...  (Alembic)
    TEST_DATABASE_URL: str = ""            # optional separate test DB

    # ── JWT ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ──────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Storage ───────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"         # local | s3
    LOCAL_STORAGE_PATH: str = "./evidence_storage"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── Scoring ───────────────────────────────────────────────────
    SCORE_LOCATION_WEIGHT: float = 20.0
    SCORE_TIMELINE_WEIGHT: float = 15.0
    SCORE_MEDIA_WEIGHT: float = 20.0
    SCORE_FINANCIAL_WEIGHT: float = 20.0
    SCORE_IDENTITY_WEIGHT: float = 10.0
    SCORE_AUDIT_WEIGHT: float = 15.0

    # ── NGO Transparency Score Model Weights ───────────────────────
    NGO_SCORE_WEIGHT_EVIDENCE_QUALITY: float = 0.35
    NGO_SCORE_WEIGHT_VALUE_VERIFICATION: float = 0.25
    NGO_SCORE_WEIGHT_AUDIT_PERFORMANCE: float = 0.20
    NGO_SCORE_WEIGHT_DISPUTE_IMPACT: float = 0.10
    NGO_SCORE_WEIGHT_HISTORICAL_TREND: float = 0.10

    # ── Risk Assessment Engine Weights ─────────────────────────────
    RISK_WEIGHT_LOCATION_MISMATCH: float = 25.0
    RISK_WEIGHT_FINANCIAL_DISCREPANCY: float = 25.0
    RISK_WEIGHT_DUPLICATE_MEDIA: float = 20.0
    RISK_WEIGHT_SUSPICIOUS_METADATA: float = 15.0
    RISK_WEIGHT_MISSING_TIMELINE: float = 15.0
    RISK_WEIGHT_FAILED_SUBMISSIONS: float = 10.0
    RISK_WEIGHT_HIGH_PROJECT_VALUE: float = 10.0
    RISK_WEIGHT_PREVIOUS_DISPUTES: float = 15.0
    RISK_WEIGHT_UNUSUAL_PATTERNS: float = 10.0
    RISK_WEIGHT_INCOMPLETE_EVIDENCE: float = 10.0

    # ── Audit Trigger Thresholds ──────────────────────────────────
    HIGH_PROJECT_VALUE_THRESHOLD: float = 1000000.0   # Projects >= 1,000,000 (10 Lakhs)
    AUDIT_RANDOM_SAMPLE_RATE: float = 0.05            # 5% random sampling probability

    # ── Seed admin ────────────────────────────────────────────────
    ADMIN_EMAIL: EmailStr = "admin@example.com"
    ADMIN_PASSWORD: str = "ChangeMe123!"
    ADMIN_FULL_NAME: str = "Platform Administrator"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
