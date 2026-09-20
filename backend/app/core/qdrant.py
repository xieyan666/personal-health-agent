"""Shared asynchronous Qdrant client and health check."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from backend.app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

# httpx, used by AsyncQdrantClient, binds its transport resources to the event
# loop that first uses it.  Keep one client per active loop so a completed
# request loop cannot leave a process-wide client bound to a closed loop.
qdrant_client: Optional[AsyncQdrantClient] = None
_qdrant_client_loop: Optional[asyncio.AbstractEventLoop] = None


def _create_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )


def get_qdrant_client() -> AsyncQdrantClient:
    """Return the shared Qdrant client for the current asynchronous loop."""
    global qdrant_client, _qdrant_client_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if qdrant_client is None or (
        current_loop is not None
        and _qdrant_client_loop is not None
        and _qdrant_client_loop is not current_loop
    ):
        qdrant_client = _create_qdrant_client()
        _qdrant_client_loop = current_loop

    return qdrant_client


async def close_qdrant() -> None:
    """Close the shared Qdrant client's HTTP resources."""
    global qdrant_client, _qdrant_client_loop

    client = qdrant_client
    qdrant_client = None
    _qdrant_client_loop = None
    if client is not None:
        await client.close()


async def check_qdrant_connection(
    client: Optional[AsyncQdrantClient] = None,
) -> bool:
    """Return whether Qdrant responds to a lightweight collections request."""
    target = client if client is not None else get_qdrant_client()
    try:
        await target.get_collections()
    except (ResponseHandlingException, UnexpectedResponse):
        logger.exception("Qdrant connection check failed")
        return False
    return True
