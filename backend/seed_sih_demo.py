"""
SIH Demonstration Dataset Seeder CLI.

Usage:
    python seed_sih_demo.py
    python seed_sih_demo.py --sqlite

Populates all fictional demonstration NGOs, personas, projects (Scenarios A, B, C, D),
evidence files, risk evaluations, audit decisions, and historical score trends.
Supports both PostgreSQL (default) and SQLite standalone demo mode.
"""
import asyncio
import os
import sys

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine, Base
from app.demo.service import seed_sih_demonstration_data

settings = get_settings()


async def seed_with_session(session_maker, custom_engine=None):
    async with session_maker() as session:
        result = await seed_sih_demonstration_data(session)

    print("\n[SUCCESS] Demonstration dataset loaded successfully!\n")
    print("DEMO PERSONAS & CREDENTIALS:")
    print("-" * 75)
    for p in result["personas"]:
        print(f" • {p['role']:<25} | {p['name']:<22} | {p['email']:<28} | {p['password']}")

    print("\nDEMONSTRATION PROJECTS & SCENARIOS:")
    print("-" * 75)
    for prj in result["projects"]:
        print(f" • [{prj['code']}] {prj['title']:<28} | Scenario: {prj['scenario']:<20} | Status: {prj['status']:<18} | Score: {prj['score']}/100 | Risk: {prj['risk']}")

    print("\nAll assets, binary evidence files, invoices, and score trends are ready for live demo.\n")
    if custom_engine:
        await custom_engine.dispose()


async def run_sqlite_seeder():
    print("\nInitializing standalone SQLite demo database (demo_sih.db)...")
    from sqlalchemy import event
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"

    sqlite_engine = create_async_engine("sqlite+aiosqlite:///./demo_sih.db", echo=False)

    @event.listens_for(sqlite_engine.sync_engine, "connect")
    def register_spatial_mocks(dbapi_connection, connection_record):
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

    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    await seed_with_session(session_maker, sqlite_engine)


async def main():
    print("=" * 75)
    print(" Smart India Hackathon (SIH) Demonstration Dataset Seeder")
    print("=" * 75)
    print(f"Target Environment: {settings.APP_ENV}")

    use_sqlite = "--sqlite" in sys.argv

    if use_sqlite:
        await run_sqlite_seeder()
        return

    print("Attempting to seed configured database (PostgreSQL)...")
    try:
        await seed_with_session(AsyncSessionLocal)
    except Exception as exc:
        err_msg = str(exc)
        if "1225" in err_msg or "connection refused" in err_msg.lower() or "could not connect" in err_msg.lower():
            print(f"\n[INFO] Configured database not reachable ({exc}).")
            print("Seamlessly falling back to standalone SQLite demo database...")
            await run_sqlite_seeder()
        else:
            print(f"\n[ERROR] Seeding error: {exc}")
            sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
