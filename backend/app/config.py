from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    APP_NAME: str = "NGO Transparency Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ───────────────────────────────────────────────
    # Defaults provided for development/testing out-of-the-box
    DATABASE_URL: str = "postgresql+asyncpg://ngo_user:ngo_secret@localhost:5432/ngo_platform"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://ngo_user:ngo_secret@localhost:5432/ngo_platform"

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "phase1_super_secret_dev_key_must_be_overridden_in_production_32chars!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Storage ───────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./evidence_storage"

    # ── Seed Admin ────────────────────────────────────────────
    ADMIN_EMAIL: EmailStr = "admin@example.com"
    ADMIN_PASSWORD: str = "ChangeMe123!"


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance (reads .env once)."""
    return Settings()
