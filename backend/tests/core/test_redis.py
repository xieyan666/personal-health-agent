"""Real Redis infrastructure tests without persistent business keys."""

from __future__ import annotations

from redis.asyncio import Redis

from backend.app.core.redis import (
    check_redis_connection,
    get_redis_client,
)


TEST_KEY = "personal_health:test:redis"


async def test_shared_client_and_real_redis_round_trip() -> None:
    first = get_redis_client()
    second = get_redis_client()
    assert first is second
    assert await check_redis_connection() is True

    try:
        assert await first.set(TEST_KEY, "connected") is True
        assert await first.get(TEST_KEY) == "connected"
    finally:
        await first.delete(TEST_KEY)
    assert await first.exists(TEST_KEY) == 0


async def test_unreachable_redis_returns_false() -> None:
    unreachable = Redis.from_url(
        "redis://127.0.0.1:1/0",
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )
    try:
        assert await check_redis_connection(unreachable) is False
    finally:
        await unreachable.aclose()
