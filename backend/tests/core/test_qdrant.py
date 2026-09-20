"""Real Qdrant infrastructure tests using one temporary collection."""

from __future__ import annotations

from uuid import uuid4

from qdrant_client import AsyncQdrantClient, models

from backend.app.core.qdrant import (
    check_qdrant_connection,
    get_qdrant_client,
)


COLLECTION_PREFIX = "personal_health_test_qdrant"


async def test_qdrant_collection_vector_lifecycle() -> None:
    collection_name = f"{COLLECTION_PREFIX}_{uuid4().hex}"
    first = get_qdrant_client()
    second = get_qdrant_client()
    assert first is second
    assert await check_qdrant_connection() is True

    collection_created = False
    try:
        assert await first.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=4,
                distance=models.Distance.COSINE,
            ),
        ) is True
        collection_created = True
        await first.upsert(
            collection_name=collection_name,
            wait=True,
            points=[
                models.PointStruct(
                    id=1,
                    vector=[0.1, 0.2, 0.3, 0.4],
                    payload={"type": "test"},
                ),
                models.PointStruct(
                    id=2,
                    vector=[0.2, 0.1, 0.4, 0.3],
                    payload={"type": "test"},
                ),
            ],
        )
        result = await first.query_points(
            collection_name=collection_name,
            query=[0.1, 0.2, 0.3, 0.4],
            limit=2,
            with_payload=True,
        )
        assert len(result.points) == 2
        assert result.points[0].id in {1, 2}
        assert isinstance(result.points[0].score, float)
        assert result.points[0].payload == {"type": "test"}
    finally:
        if collection_created:
            await first.delete_collection(collection_name)

    remaining = {item.name for item in (await first.get_collections()).collections}
    assert collection_name not in remaining


async def test_unreachable_qdrant_returns_false() -> None:
    unreachable = AsyncQdrantClient(url="http://127.0.0.1:1", timeout=0.2)
    try:
        assert await check_qdrant_connection(unreachable) is False
    finally:
        await unreachable.close()
