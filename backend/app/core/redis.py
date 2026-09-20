"""Shared asynchronous Redis client and health check."""

from __future__ import annotations

import logging
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

redis_client: Redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


def get_redis_client() -> Redis:
    """Return the single process-wide asynchronous Redis client."""
    return redis_client


async def close_redis() -> None:
    """Close the shared client and release its connection pool."""
    await redis_client.aclose()


async def check_redis_connection(client: Optional[Redis] = None) -> bool:
    """Return whether Redis responds successfully to PING.

    The optional client is intended for isolated failure-path verification;
    normal application code always uses the shared global client.
    """
    target = client if client is not None else redis_client
    try:
        return bool(await target.ping())
    except RedisError:
        logger.exception("Redis connection check failed")
        return False
