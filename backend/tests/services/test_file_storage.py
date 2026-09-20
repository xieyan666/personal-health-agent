"""Real MinIO tests for the knowledge-file storage business service."""

from __future__ import annotations

from uuid import uuid4

import pytest

import backend.app.services.file_storage as storage_module
from backend.app.services import FileStorageService
from backend.app.services.exceptions import ConflictError, NotFoundError, ValidationError


TEST_CONTENT = b"Personal Health Agent storage test"


def remove_if_present(service: FileStorageService, object_key: str) -> None:
    if service.object_exists(object_key):
        service.delete_file(object_key)


def test_ensure_knowledge_bucket_is_idempotent() -> None:
    service = FileStorageService()
    assert service.ensure_bucket() == service.settings.minio_knowledge_bucket
    assert service.client.bucket_exists(service.bucket) is True
    assert service.ensure_bucket() == service.bucket
    assert service.client.bucket_exists(service.bucket) is True


def test_upload_get_stat_exists_delete_and_allowed_extensions() -> None:
    service = FileStorageService()
    created_keys: list[str] = []
    knowledge_base_id = uuid4()
    try:
        for suffix, expected_type in {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.items():
            document_id = uuid4()
            original_name = f"My Health File{suffix}"
            stored = service.upload_file(
                knowledge_base_id,
                document_id,
                original_name,
                TEST_CONTENT,
                len(TEST_CONTENT),
            )
            created_keys.append(stored.object_key)
            expected_prefix = f"knowledge/{knowledge_base_id}/{document_id}/"
            assert stored.bucket == service.bucket
            assert stored.object_key.startswith(expected_prefix)
            assert original_name not in stored.object_key
            assert stored.object_key.endswith(suffix)
            assert stored.size == len(TEST_CONTENT)
            assert stored.content_type == expected_type
            assert service.object_exists(stored.object_key) is True
            assert service.get_file(stored.object_key) == TEST_CONTENT
            stat = service.stat_file(stored.object_key)
            assert stat.object_key == stored.object_key
            assert stat.size == len(TEST_CONTENT)
            assert stat.content_type == expected_type

        first = service.upload_file(
            knowledge_base_id,
            uuid4(),
            "test.txt",
            TEST_CONTENT,
            len(TEST_CONTENT),
        )
        second = service.upload_file(
            knowledge_base_id,
            uuid4(),
            "test.txt",
            TEST_CONTENT,
            len(TEST_CONTENT),
        )
        created_keys.extend([first.object_key, second.object_key])
        assert first.object_key != second.object_key
    finally:
        for object_key in created_keys:
            remove_if_present(service, object_key)
    assert service.client.bucket_exists(service.bucket) is True


def test_validation_and_path_injection_protection() -> None:
    service = FileStorageService()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    for filename in ("file.exe", "file.zip", "file.html", "no-extension"):
        with pytest.raises(ValidationError):
            service.upload_file(
                knowledge_base_id,
                document_id,
                filename,
                TEST_CONTENT,
                len(TEST_CONTENT),
            )
    with pytest.raises(ValidationError):
        service.upload_file(
            knowledge_base_id,
            document_id,
            "large.pdf",
            b"",
            service.max_size_bytes + 1,
        )

    created_keys: list[str] = []
    try:
        for filename in ("../../evil.txt", "..\\..\\evil.txt"):
            stored = service.upload_file(
                knowledge_base_id,
                uuid4(),
                filename,
                TEST_CONTENT,
                len(TEST_CONTENT),
            )
            created_keys.append(stored.object_key)
            assert ".." not in stored.object_key
            assert "\\" not in stored.object_key
            assert "evil.txt" not in stored.object_key
    finally:
        for object_key in created_keys:
            remove_if_present(service, object_key)

    for unsafe_key in ("../evil.txt", "/knowledge/evil.txt", "knowledge\\evil.txt"):
        with pytest.raises(ValidationError):
            service.object_exists(unsafe_key)


def test_no_overwrite_and_missing_object_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FileStorageService()
    knowledge_base_id = uuid4()
    document_id = uuid4()
    fixed_key = storage_module.build_knowledge_object_key(
        knowledge_base_id, document_id, ".txt"
    )
    monkeypatch.setattr(
        storage_module,
        "build_knowledge_object_key",
        lambda _knowledge_base_id, _document_id, _suffix: fixed_key,
    )
    try:
        first = service.upload_file(
            knowledge_base_id,
            document_id,
            "test.txt",
            TEST_CONTENT,
            len(TEST_CONTENT),
        )
        assert first.object_key == fixed_key
        with pytest.raises(ConflictError):
            service.upload_file(
                knowledge_base_id,
                document_id,
                "test.txt",
                b"replacement",
                len(b"replacement"),
            )
        assert service.get_file(fixed_key) == TEST_CONTENT
        service.delete_file(fixed_key)
        assert service.object_exists(fixed_key) is False
        with pytest.raises(NotFoundError):
            service.delete_file(fixed_key)
        with pytest.raises(NotFoundError):
            service.get_file(fixed_key)
        with pytest.raises(NotFoundError):
            service.stat_file(fixed_key)
    finally:
        remove_if_present(service, fixed_key)
    assert service.client.bucket_exists(service.bucket) is True
