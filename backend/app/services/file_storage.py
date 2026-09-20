"""Business rules for private MinIO knowledge-file objects."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import BinaryIO, Dict, Union
from uuid import UUID, uuid4

from minio import Minio
from minio.error import InvalidResponseError, S3Error, ServerError
from urllib3.exceptions import HTTPError

from backend.app.core.config import Settings, get_settings
from backend.app.core.minio import get_minio_client
from backend.app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)


ALLOWED_KNOWLEDGE_FILE_TYPES: Dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_KNOWLEDGE_FILE_EXTENSIONS = frozenset(ALLOWED_KNOWLEDGE_FILE_TYPES)
NOT_FOUND_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchBucket", "XMinioInvalidObjectName"}
MINIO_ERRORS = (S3Error, InvalidResponseError, ServerError, HTTPError, OSError)
KNOWLEDGE_OBJECT_KEY_PATTERN = re.compile(
    r"^knowledge/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f]{32}"
    r"(?:\.txt|\.md|\.pdf|\.docx)$"
)


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_key: str
    size: int
    content_type: str
    etag: str | None = None


def build_knowledge_object_key(
    knowledge_base_id: UUID, document_id: UUID, suffix: str
) -> str:
    """Build a system-owned object key with a random stored filename."""
    normalized_suffix = suffix.lower()
    if normalized_suffix not in ALLOWED_KNOWLEDGE_FILE_EXTENSIONS:
        raise ValidationError(f"Unsupported knowledge file extension: {suffix}")
    return (
        f"knowledge/{knowledge_base_id}/{document_id}/"
        f"{uuid4().hex}{normalized_suffix}"
    )


class FileStorageService:
    """Store original knowledge files in the configured private MinIO bucket."""

    def __init__(
        self,
        client: Minio | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.client = client if client is not None else get_minio_client()
        self.settings = settings if settings is not None else get_settings()
        self.bucket = self.settings.minio_knowledge_bucket
        self.max_size_bytes = self.settings.max_knowledge_file_size_mb * 1024 * 1024

    def ensure_bucket(self) -> str:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except MINIO_ERRORS as exc:
            raise ServiceError("Unable to initialize knowledge file bucket") from exc
        return self.bucket

    def upload_file(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        original_filename: str,
        data: Union[bytes, BinaryIO],
        size: int,
    ) -> StoredObject:
        suffix = self._validate_filename(original_filename)
        self._validate_size(size)
        object_key = build_knowledge_object_key(
            knowledge_base_id, document_id, suffix
        )
        self.ensure_bucket()
        if self.object_exists(object_key):
            raise ConflictError(f"Knowledge object already exists: {object_key}")

        stream = BytesIO(data) if isinstance(data, bytes) else data
        if isinstance(data, bytes) and len(data) != size:
            raise ValidationError("Declared file size does not match file data")
        content_type = ALLOWED_KNOWLEDGE_FILE_TYPES[suffix]
        try:
            result = self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_key,
                data=stream,
                length=size,
                content_type=content_type,
            )
        except MINIO_ERRORS as exc:
            raise ServiceError("Unable to upload knowledge file") from exc
        return StoredObject(
            bucket=self.bucket,
            object_key=object_key,
            size=size,
            content_type=content_type,
            etag=result.etag,
        )

    def get_file(self, object_key: str) -> bytes:
        self._validate_object_key(object_key)
        try:
            response = self.client.get_object(self.bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            self._raise_object_error(exc, object_key, "read")
        except (InvalidResponseError, ServerError, HTTPError, OSError) as exc:
            raise ServiceError("Unable to read knowledge file") from exc

    def stat_file(self, object_key: str) -> StoredObject:
        self._validate_object_key(object_key)
        try:
            stat = self.client.stat_object(self.bucket, object_key)
        except S3Error as exc:
            self._raise_object_error(exc, object_key, "stat")
        except (InvalidResponseError, ServerError, HTTPError, OSError) as exc:
            raise ServiceError("Unable to stat knowledge file") from exc
        return StoredObject(
            bucket=self.bucket,
            object_key=object_key,
            size=stat.size,
            content_type=stat.content_type,
            etag=stat.etag,
        )

    def object_exists(self, object_key: str) -> bool:
        self._validate_object_key(object_key)
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in NOT_FOUND_CODES:
                return False
            raise ServiceError("Unable to check knowledge file") from exc
        except (InvalidResponseError, ServerError, HTTPError, OSError) as exc:
            raise ServiceError("Unable to check knowledge file") from exc

    def delete_file(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        if not self.object_exists(object_key):
            raise NotFoundError(f"Knowledge object not found: {object_key}")
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error as exc:
            self._raise_object_error(exc, object_key, "delete")
        except (InvalidResponseError, ServerError, HTTPError, OSError) as exc:
            raise ServiceError("Unable to delete knowledge file") from exc

    @staticmethod
    def _validate_filename(original_filename: str) -> str:
        safe_name = original_filename.replace("\\", "/")
        suffix = PurePosixPath(safe_name).suffix.lower()
        if suffix not in ALLOWED_KNOWLEDGE_FILE_EXTENSIONS:
            raise ValidationError(f"Unsupported knowledge file extension: {suffix}")
        return suffix

    def _validate_size(self, size: int) -> None:
        if size < 0:
            raise ValidationError("File size must be greater than or equal to 0")
        if size > self.max_size_bytes:
            raise ValidationError(
                f"Knowledge file exceeds {self.settings.max_knowledge_file_size_mb} MB"
            )

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        if KNOWLEDGE_OBJECT_KEY_PATTERN.fullmatch(object_key) is None:
            raise ValidationError("Invalid knowledge object key")

    @staticmethod
    def _raise_object_error(exc: S3Error, object_key: str, operation: str) -> None:
        if exc.code in NOT_FOUND_CODES:
            raise NotFoundError(f"Knowledge object not found: {object_key}") from exc
        raise ServiceError(f"Unable to {operation} knowledge file") from exc


def ensure_knowledge_bucket() -> str:
    """Idempotently initialize the configured private knowledge bucket."""
    return FileStorageService().ensure_bucket()
