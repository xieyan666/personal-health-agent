"""Private, current-user avatar storage backed by the existing MinIO service."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

from minio.error import InvalidResponseError, S3Error, ServerError
from urllib3.exceptions import HTTPError

from backend.app.core.minio import get_minio_client
from backend.app.exceptions import ServiceError, ValidationError

AVATAR_BUCKET = "user-avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
PREFIX = "avatars/"
MINIO_ERRORS = (S3Error, InvalidResponseError, ServerError, HTTPError, OSError)


class AvatarStorageService:
    """Stores only images owned by the currently authenticated employee."""

    def __init__(self) -> None:
        self.client = get_minio_client()

    def upload(self, *, user_id: UUID, content_type: str | None, data: bytes) -> str:
        media_type = (content_type or "").lower()
        if media_type not in ALLOWED_TYPES:
            raise ValidationError("头像仅支持 JPG、PNG 或 WebP 图片")
        if not data:
            raise ValidationError("头像文件不能为空")
        if len(data) > MAX_AVATAR_BYTES:
            raise ValidationError("头像文件不能超过 5MB")
        object_key = f"{PREFIX}{user_id}/{uuid4().hex}{ALLOWED_TYPES[media_type]}"
        try:
            if not self.client.bucket_exists(AVATAR_BUCKET):
                self.client.make_bucket(AVATAR_BUCKET)
            self.client.put_object(
                AVATAR_BUCKET,
                object_key,
                BytesIO(data),
                len(data),
                content_type=media_type,
            )
        except MINIO_ERRORS as exc:
            raise ServiceError("头像上传失败") from exc
        return object_key

    def read(self, object_key: str) -> tuple[bytes, str]:
        if not object_key.startswith(PREFIX):
            raise ValidationError("无效的头像文件")
        try:
            response = self.client.get_object(AVATAR_BUCKET, object_key)
            try:
                return response.read(), response.headers.get("Content-Type", "image/jpeg")
            finally:
                response.close()
                response.release_conn()
        except MINIO_ERRORS as exc:
            raise ServiceError("头像读取失败") from exc

    def delete(self, object_key: str | None) -> None:
        if not object_key or not object_key.startswith(PREFIX):
            return
        try:
            self.client.remove_object(AVATAR_BUCKET, object_key)
        except MINIO_ERRORS:
            # Replacing an avatar must not fail merely because an old object
            # has already been cleaned up by MinIO lifecycle policy.
            return
