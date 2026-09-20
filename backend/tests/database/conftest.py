"""Real PostgreSQL fixtures with per-test transaction rollback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession


def _load_test_environment() -> None:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        raise RuntimeError(f"Required test environment file does not exist: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


_load_test_environment()

from backend.app.core.database import engine  # noqa: E402


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Run each test in an outer transaction that is always rolled back."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
    await engine.dispose()
