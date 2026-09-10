"""
Test configuration and fixtures for Phase 1 backend foundation.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import AsyncGenerator

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set testing environment variables before importing app
os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_jwt_key_at_least_32_characters_long!"


import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password

from app.main import app as fastapi_app



from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
# Map Postgres JSONB to SQLite TEXT for in-memory testing
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"


@pytest_asyncio.fixture(scope="session")
async def test_engine():

    from sqlalchemy import event

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Register mock GeoAlchemy2 spatialite functions on aiosqlite connection worker thread
    @event.listens_for(engine.sync_engine, "connect")
    def register_sqlite_spatial_funcs(dbapi_connection, connection_record):
        raw_aiosqlite = getattr(dbapi_connection, "_connection", None)
        if raw_aiosqlite and hasattr(dbapi_connection, "await_"):
            dbapi_connection.await_(raw_aiosqlite.create_function("RecoverGeometryColumn", 5, lambda *a: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("InitSpatialMetaData", 0, lambda: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("InitSpatialMetaData", 1, lambda *a: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("DiscardGeometryColumn", 2, lambda *a: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("CreateSpatialIndex", 2, lambda *a: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("DisableSpatialIndex", 2, lambda *a: 1))
            dbapi_connection.await_(raw_aiosqlite.create_function("GeomFromEWKT", 1, lambda val: val))
            dbapi_connection.await_(raw_aiosqlite.create_function("GeomFromText", 1, lambda val: val))
            dbapi_connection.await_(raw_aiosqlite.create_function("GeomFromText", 2, lambda val, srid: val))
            import struct
            dummy_ewkb = struct.pack('<bIIdd', 1, 0x20000001, 4326, 0.0, 0.0)
            dbapi_connection.await_(raw_aiosqlite.create_function("AsEWKB", 1, lambda val: None if val is None else dummy_ewkb))
            dbapi_connection.await_(raw_aiosqlite.create_function("AsBinary", 1, lambda val: None if val is None else dummy_ewkb))
            dbapi_connection.await_(raw_aiosqlite.create_function("AsEWKT", 1, lambda val: str(val)))
            dbapi_connection.await_(raw_aiosqlite.create_function("AsText", 1, lambda val: str(val)))





    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()





@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()



@pytest.fixture
def auth_headers():
    def _make_headers(user_id: uuid.UUID | str, role: str = "DONOR", email: str = "user@test.com") -> dict[str, str]:
        token = create_access_token(
            subject=str(user_id),
            extra={"role": role, "email": email},
        )
        return {"Authorization": f"Bearer {token}"}
    return _make_headers
