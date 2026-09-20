"""Shared synchronous MinIO client and health check."""

from __future__ import annotations

import logging
from typing import Optional

from minio import Minio
from minio.error import InvalidResponseError, S3Error, ServerError
from urllib3.exceptions import HTTPError

from backend.app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

minio_client = Minio(
    endpoint=settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def get_minio_client() -> Minio:
    """Return the single process-wide synchronous MinIO client."""
    return minio_client


def check_minio_connection(client: Optional[Minio] = None) -> bool:
    """Return whether MinIO responds to an authenticated list-buckets call."""
    target = client if client is not None else minio_client
    try:
        target.list_buckets()
    except (S3Error, InvalidResponseError, ServerError, HTTPError, OSError):
        logger.exception("MinIO connection check failed")
        return False
    return True
