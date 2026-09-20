"""Minimal application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Infrastructure settings required by the backend."""

    database_url: str
    redis_url: str
    qdrant_url: str
    qdrant_api_key: Optional[str]
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_knowledge_bucket: str
    max_knowledge_file_size_mb: int

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is required")
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL environment variable is required")
        if not redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use the redis or rediss scheme")
        qdrant_url = os.getenv("QDRANT_URL")
        if not qdrant_url:
            raise RuntimeError("QDRANT_URL environment variable is required")
        if not qdrant_url.startswith(("http://", "https://")):
            raise ValueError("QDRANT_URL must use the http or https scheme")
        qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
        minio_endpoint = os.getenv("MINIO_ENDPOINT")
        if not minio_endpoint:
            raise RuntimeError("MINIO_ENDPOINT environment variable is required")
        if "://" in minio_endpoint:
            raise ValueError("MINIO_ENDPOINT must contain only host:port")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        if not minio_access_key:
            raise RuntimeError("MINIO_ACCESS_KEY environment variable is required")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        if not minio_secret_key:
            raise RuntimeError("MINIO_SECRET_KEY environment variable is required")
        minio_secure_raw = os.getenv("MINIO_SECURE", "false").lower()
        if minio_secure_raw not in {"true", "false"}:
            raise ValueError("MINIO_SECURE must be true or false")
        minio_knowledge_bucket = os.getenv(
            "MINIO_KNOWLEDGE_BUCKET", "knowledge-files"
        )
        if not minio_knowledge_bucket:
            raise ValueError("MINIO_KNOWLEDGE_BUCKET must not be empty")
        max_file_size_raw = os.getenv("MAX_KNOWLEDGE_FILE_SIZE_MB", "20")
        try:
            max_knowledge_file_size_mb = int(max_file_size_raw)
        except ValueError as exc:
            raise ValueError("MAX_KNOWLEDGE_FILE_SIZE_MB must be an integer") from exc
        if max_knowledge_file_size_mb < 1:
            raise ValueError("MAX_KNOWLEDGE_FILE_SIZE_MB must be greater than 0")
        return cls(
            database_url=database_url,
            redis_url=redis_url,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            minio_endpoint=minio_endpoint,
            minio_access_key=minio_access_key,
            minio_secret_key=minio_secret_key,
            minio_secure=minio_secure_raw == "true",
            minio_knowledge_bucket=minio_knowledge_bucket,
            max_knowledge_file_size_mb=max_knowledge_file_size_mb,
        )


def get_settings() -> Settings:
    """Build settings from the current process environment."""

    return Settings.from_environment()
