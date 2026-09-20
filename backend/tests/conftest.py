"""Root pytest configuration: isolate every test onto a dedicated database.

Why this exists: the MCP / multi-agent agent tests (tests/agent/test_runtime_mcp*.py,
test_multi_agent*.py) create ``mcp-*`` / ``multi-agent-*`` users through the shared
``AsyncSessionFactory``.  Previously that pointed at the *development* database and
their cleanup teardown did not always run (stdio MCP servers fail to start), leaving
thousands of test users behind.

This module runs before any test module imports backend code and:

1. creates a dedicated ``life_health_test`` database;
2. rebinds the shared engine + session factory to it;
3. creates the schema once per session and drops the database afterwards.

The production users table can therefore never be touched by pytest.
"""

from __future__ import annotations

import asyncio
import os
import re

_BASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://life_health:LhaDev_2026_8f4c2a91@postgres:5432/life_health",
)
_TEST_DB = "life_health_test"
_MATCH = re.match(r"^(postgresql\+asyncpg://[^/]+)/[^?]*(\?.*)?$", _BASE_URL)
assert _MATCH is not None, f"cannot parse DATABASE_URL: {_BASE_URL}"
_ADMIN_URL = f"{_MATCH.group(1)}/postgres{_MATCH.group(2) or ''}"
_TEST_URL = f"{_MATCH.group(1)}/{_TEST_DB}{_MATCH.group(2) or ''}"


def _create_test_database() -> None:
    import asyncpg

    async def _run() -> None:
        connection = await asyncpg.connect(_ADMIN_URL.replace("+asyncpg", ""))
        try:
            exists = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB
            )
            if not exists:
                await connection.execute(f'CREATE DATABASE "{_TEST_DB}"')
        finally:
            await connection.close()

    asyncio.run(_run())


_create_test_database()
os.environ["DATABASE_URL"] = _TEST_URL

# Rebind the shared engine + session factory BEFORE any test module imports
# them (the settings singleton caches the old URL, so rebind explicitly).
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

import backend.app.core.database as _database  # noqa: E402

_database.engine = create_async_engine(_TEST_URL, pool_pre_ping=True)
_database.AsyncSessionFactory = async_sessionmaker(
    bind=_database.engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

import pytest  # noqa: E402
from backend.app.models.base import Base  # noqa: E402


async def _create_schema() -> None:
    async with _database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    # Release the connections created inside this temporary loop so the pool
    # never hands a cross-loop asyncpg connection to pytest-asyncio's loop.
    await _database.engine.dispose()


# Build the schema once at import time (avoids the pytest-asyncio function
# scoped event_loop vs session fixture ScopeMismatch).
asyncio.run(_create_schema())


@pytest.fixture(scope="session", autouse=True)
def _test_database_teardown():
    yield
    import asyncio as _asyncio

    async def _teardown() -> None:
        await _database.engine.dispose()
        try:
            import asyncpg
            connection = await asyncpg.connect(_ADMIN_URL.replace("+asyncpg", ""))
            try:
                await connection.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB}" WITH (FORCE)')
            finally:
                await connection.close()
        except Exception:
            pass

    _asyncio.run(_teardown())
