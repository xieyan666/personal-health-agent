"""Real MinIO infrastructure tests using one unique temporary bucket."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import urllib3
from minio import Minio
from minio.error import S3Error

from backend.app.core.minio import check_minio_connection, get_minio_client


BUCKET_PREFIX = "personal-health-test"
OBJECT_NAME = "test.txt"
OBJECT_CONTENT = b"Personal Health Agent MinIO test"


def test_minio_bucket_object_lifecycle() -> None:
    bucket_name = f"{BUCKET_PREFIX}-{uuid4().hex}"
    first = get_minio_client()
    second = get_minio_client()
    assert first is second
    assert check_minio_connection() is True

    bucket_created = False
    object_uploaded = False
    try:
        first.make_bucket(bucket_name)
        bucket_created = True
        assert first.bucket_exists(bucket_name) is True

        first.put_object(
            bucket_name=bucket_name,
            object_name=OBJECT_NAME,
            data=BytesIO(OBJECT_CONTENT),
            length=len(OBJECT_CONTENT),
            content_type="text/plain",
        )
        object_uploaded = True

        response = first.get_object(bucket_name, OBJECT_NAME)
        try:
            downloaded = response.read()
        finally:
            response.close()
            response.release_conn()
        assert downloaded == OBJECT_CONTENT
        assert len(downloaded) == len(OBJECT_CONTENT)

        stat = first.stat_object(bucket_name, OBJECT_NAME)
        assert stat.object_name == OBJECT_NAME
        assert stat.size == len(OBJECT_CONTENT)

        first.remove_object(bucket_name, OBJECT_NAME)
        object_uploaded = False
        try:
            first.stat_object(bucket_name, OBJECT_NAME)
        except S3Error as exc:
            assert exc.code in {"NoSuchKey", "NoSuchObject"}
        else:
            raise AssertionError("Removed test object still exists")
    finally:
        if object_uploaded:
            first.remove_object(bucket_name, OBJECT_NAME)
        if bucket_created:
            first.remove_bucket(bucket_name)

    assert first.bucket_exists(bucket_name) is False


def test_unreachable_minio_returns_false() -> None:
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=0.2, read=0.2),
        retries=urllib3.Retry(total=0),
    )
    unreachable = Minio(
        endpoint="127.0.0.1:1",
        access_key="test-access",
        secret_key="test-secret",
        secure=False,
        http_client=http_client,
    )
    try:
        assert check_minio_connection(unreachable) is False
    finally:
        http_client.clear()
