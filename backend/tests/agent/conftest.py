"""Reuse committed PostgreSQL service fixture for agent runtime tests."""

from backend.tests.services.conftest import service_context

__all__ = ["service_context"]
