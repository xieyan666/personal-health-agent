"""Reuse the real PostgreSQL rollback fixture from database tests."""

from backend.tests.database.conftest import db_session

__all__ = ["db_session"]
