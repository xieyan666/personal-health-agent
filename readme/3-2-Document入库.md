# 1. 完成内容

完成 Document 文件上传入库、PostgreSQL metadata、MinIO Object 关联、下载、删除、状态管理和跨存储补偿。

- 新增 `DocumentIngestionService`，集中协调 PostgreSQL Document 与 MinIO Object。
- 继续复用 3-1 的 `FileStorageService` 和 `knowledge-files` Bucket。
- Document Object Locator 使用现有 `documents.source_reference` JSONB 字段；前置数据库设计明确该字段用于 MinIO object key、URL、外部 ID。
- 未修改 SQLAlchemy Model、Alembic Migration、PostgreSQL Schema、Redis、Qdrant 或 MinIO 基础设施架构。
- 未实现 Parser、Chunk、Embedding、Qdrant 索引、RAG、OCR、后台任务或 Agent Runtime。

# 2. 新增/修改文件

新增文件：

- `backend/app/services/document_ingestion.py`
- `backend/app/schemas/document.py`
- `backend/app/api/routes/documents.py`
- `backend/tests/api/test_documents.py`
- `readme/3-2-Document入库.md`

修改文件：

- `backend/app/services/__init__.py`
- `backend/app/api/deps.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/main.py`
- `backend/tests/api/conftest.py`
- `backend/requirements.txt`：增加 `python-multipart` 支持 FastAPI UploadFile。

# 3. Document 入库架构

Document Model 使用的 Object Key 字段：

```text
documents.source_reference["object_key"]
documents.source_reference["bucket"]
```

该字段在数据库设计中已定义为来源引用，语义覆盖 MinIO Object Locator；没有新增列、没有修改 Migration，也没有把 Key 塞入无关字段。

职责划分：

- FileStorageService：只负责 MinIO Object。
- DocumentRepository：只负责 `documents` 表。
- DocumentService：保留原有 metadata Service。
- DocumentIngestionService：协调 PostgreSQL 与 MinIO 上传、下载和删除。

# 4. PostgreSQL / MinIO 关联

Document 成功入库时保存：

- `id`
- `knowledge_base_id`
- 原始文件名 `name`
- `source_type="upload"`
- `source_reference.bucket`
- `source_reference.object_key`
- `mime_type`
- `size_bytes`
- `status="stored"`
- `metadata_={}`

上传顺序：

```text
MinIO upload → PostgreSQL Document insert → commit
```

Document ID 在上传前生成，并传入 3-1 的 Object Key 生成器；Object Key 格式保持：

```text
knowledge/{knowledge_base_id}/{document_id}/{uuid_hex}{suffix}
```

# 5. Document API

Document API 路由数量：5。

- `POST /api/v1/knowledge-bases/{knowledge_base_id}/documents`
- `GET /api/v1/knowledge-bases/{knowledge_base_id}/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/content`
- `DELETE /api/v1/documents/{document_id}`

上传使用 `multipart/form-data` 的 `UploadFile`，只接受 `file` 字段。列表支持 `offset`/`limit`，范围为 offset >= 0、1 <= limit <= 100。没有新增 `POST /api/v1/documents`，没有 Document PATCH。

DocumentResponse 只返回 Document 自身公开 metadata，不返回 `source_reference`；因此客户端不会看到 MinIO bucket、object_key 或内部存储路径。Backend 下载和删除时仍从数据库内部读取 `source_reference` 定位 Object，不展开 KnowledgeBase、Chunk、Embedding 或 Qdrant 关系。

# 6. 文件上传流程

1. 校验 KnowledgeBase 存在，不存在直接返回 HTTP 404。
2. 生成 Document UUID。
3. 调用现有 FileStorageService.upload_file()。
4. MinIO 上传成功后创建 Document metadata。
5. PostgreSQL commit 成功后才返回 HTTP 201。

复用 3-1 文件规则：

- 支持 `.txt`、`.md`、`.pdf`、`.docx`。
- 最大文件大小 20 MB。
- 原始文件名只写入 PostgreSQL metadata，不作为 Object Key。
- 非法扩展名和超限请求返回 HTTP 422，上传前不会创建 Document 或 Object。

# 7. 文件下载与删除

下载：

- 先读取 Document metadata，再使用保存的 object_key 调用 FileStorageService.get_file()。
- 返回原始 bytes。
- Content-Type 使用 Document 保存的 MIME 类型。
- Content-Disposition 使用安全编码的 `filename*` attachment Header。
- Document 存在但 Object 缺失时返回 HTTP 404，Document 保留。

删除顺序：

```text
确认 Document
→ 删除 MinIO Object
→ 删除 PostgreSQL Document
→ commit
```

- 只使用数据库中的 Object Key，不接受客户端传入 bucket/object_key。
- Object 缺失时返回 HTTP 404，不静默删除数据库记录。
- MinIO 删除失败时不删除 Document。
- 数据库删除/commit 失败发生在 Object 删除后，属于明确的跨基础设施补偿边界；不引入 2PC、Saga 或消息队列。
- 正常删除返回 HTTP 204。

# 8. 跨存储一致性与补偿

数据库失败是否删除本次 MinIO Object：是。

当 MinIO upload 成功但 Document flush/commit 失败时：

1. rollback PostgreSQL Session；
2. 精确删除本次 Object；
3. 继续抛出原数据库异常；
4. 不留下 Document 或孤儿 Object。

MinIO 上传失败时不会创建 Document。真实测试使用超长数据库字段触发 PostgreSQL 失败，确认 MinIO Object 已被补偿删除。

# 9. API 测试

执行命令：

```text
python -m pytest backend/tests/api/test_documents.py -v
```

结果（本次 source_reference 响应边界修正后）：

- 专项测试总数：3
- passed：3
- failed：0
- skipped：0
- Python 实际版本：3.12.14

专项测试真实连接 FastAPI、PostgreSQL 和 MinIO，没有 Mock、skip 或 xfail。覆盖四种文件类型、上传/list/detail/download/delete、Content-Type/Disposition、上传和详情响应不包含 `source_reference`、非法扩展名、KnowledgeBase 不存在、超限、缺失 Object、缺失 Document 和数据库失败补偿。

# 10. 全量回归

执行命令：

```text
python -m pytest backend/tests -v
```

结果：

- 总测试数：52
- passed：52
- failed：0
- skipped：0
- Python 实际版本：3.12.14
- warnings：3（既有 Qdrant Client/Server 版本和不可达探测提示，以及既有 FastAPI 422 常量弃用提示）。

本次小修正后的专项与全量回归均重新执行并通过。

全量测试在自动删除的官方 `python:3.12-slim` 容器中执行，真实使用本地开发 PostgreSQL、Redis、Qdrant、MinIO；凭据未输出、记录或写入报告，容器使用 `--rm` 自动删除。

# 11. 最终数据与基础设施状态

- PostgreSQL：正常；Alembic `20260817_0001`。
- PostgreSQL Document 测试数据是否残留：否，`documents=0`。
- KnowledgeBase 测试数据是否残留：否，`knowledge_bases=0`。
- PostgreSQL 业务表统计残留：0。
- Redis：正常，测试键残留 0。
- Qdrant：正常，临时测试 Collection 残留 0。
- MinIO：正常。
- MinIO 测试 Object 是否残留：否，`knowledge-files` 对象数为 0。
- `knowledge-files` Bucket 是否保留：是。
- 临时测试 Bucket：0。

# 12. 未完成内容

按任务边界未实现：

- Parser、PDF/DOCX/Markdown/TXT 内容解析
- Chunk Model、Chunk Service、Chunk API
- Embedding、Qdrant Collection/Point、索引和检索
- RAG、OCR、后台 Job、Worker、Celery、Redis Queue
- Document PATCH、文件替换、覆盖 Object、Presigned URL
- 3-3 Chunk、3-4 Embedding、3-5 Qdrant 索引、3-6 Retrieval/RAG
