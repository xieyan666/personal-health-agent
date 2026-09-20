"""Lightweight request metrics middleware.

Records only HTTP metadata (path, method, status, duration).  Bodies,
headers, cookies, JWT and API keys are never touched, so no sensitive
material can leak into ``request_metrics``.
"""

from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import RequestMetric

# Never record internal / monitoring endpoints to avoid self-amplification.
_SKIP_PREFIXES = ("/api/v1/admin/system-monitor", "/api/v1/auth", "/health")
_MAX_PATH = 255


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return await call_next(request)
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            response = None
            raise
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            status = response.status_code if response is not None else 500
            try:
                async with AsyncSessionFactory() as session:
                    session.add(
                        RequestMetric(
                            id=uuid4(),
                            path=request.url.path[:_MAX_PATH],
                            method=request.method,
                            status_code=status,
                            duration_ms=duration_ms,
                        )
                    )
                    await session.commit()
            except Exception:
                # Metrics must never break the actual request.
                pass
        return response
