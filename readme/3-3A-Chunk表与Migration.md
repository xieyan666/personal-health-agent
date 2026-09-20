# 1. 完成内容

新增 PostgreSQL `document_chunks` 持久化结构、SQLAlchemy Model、Alembic Migration、Repository 和真实数据库/Repository 测试。

本阶段未实现 Chunk 切分、ChunkService、Chunk API、Parser、Embedding、Qdrant、RAG 或其他后续能力。

# 2. 新增/修改文件

新增：

- `backend/app/models/chunk.py`
- `backend/alembic/versions/20260818_0002_document_chunks.py`
- `backend/app/repositories/chunk.py`
- `backend/tests/database/test_chunks.py`
- `backend/tests/repositories/test_chunks.py`
- `readme/3-3A-Chunk表与Migration.md`

修改：

- `backend/app/models/knowledge.py`：增加 `Document.chunks` 关系。
- `backend/app/models/__init__.py`：导出 `DocumentChunk`。
- `backend/app/repositories/__init__.py`：导出 `DocumentChunkRepository`。

未修改 documents 现有字段、MinIO、Redis、Qdrant 或其他业务表。

# 3. 表结构

新表名：`document_chunks`

字段：

- `id UUID PRIMARY KEY`
- `document_id UUID NOT NULL`
- `chunk_index INTEGER NOT NULL`
- `content TEXT NOT NULL`
- `char_count INTEGER NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

FK：`document_id REFERENCES documents(id)`，未设置 cascade，使用默认 NO ACTION。

Unique constraint：`uq_document_chunks_document_index(document_id, chunk_index)`。

Check constraints：

- `ck_document_chunks_chunk_index`: `chunk_index >= 0`
- `ck_document_chunks_char_count`: `char_count >= 0`

Indexes：

- `ix_document_chunks_document_id(document_id)`
- `ix_document_chunks_document_id_chunk_index(document_id, chunk_index)`

未新增 embedding、vector 或 qdrant_point_id 字段。

# 4. Model 与 Repository

Model 类：`DocumentChunk`，复用现有 `Base` / `TimestampMixin`。

关系：

- `Document.chunks`
- `DocumentChunk.document`
- 未配置 delete cascade。

Repository：`DocumentChunkRepository`。

- `get_by_id()` 复用 BaseRepository。
- `list_by_document_id()` 按 `chunk_index ASC`。
- `exists_by_document_and_index()`。
- `create()` 复用 BaseRepository，只 flush。
- `delete_by_document_id()` 只删除目标 Document 的 Chunk，只 flush，不 commit。

# 5. Migration 验证

新增 Migration revision：`20260818_0002`，前置 revision：`20260817_0001`。

实际执行顺序：

```text
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

结果：三步均成功，最终数据库停留在 `20260818_0002` 最新 head，`document_chunks` 表真实存在。

# 6. 专项测试结果

实际执行：

```text
python -m pytest backend/tests/database backend/tests/repositories -v
```

最终结果：

- Python：3.12.14
- 总数：19
- passed：19
- failed：0
- skipped：0

覆盖 Chunk 创建、Document 关系、FK、chunk_index/char_count CheckConstraint、同 Document index 唯一约束、排序、目标 Document 删除和 Repository 不自行 commit。

# 7. 全量测试结果

在本次授权范围内传入本地开发 Redis、Qdrant、MinIO 参数后执行：

```text
python -m pytest backend/tests -v
```

- 总数：54
- passed：54
- failed：0
- skipped：0
- Python：3.12.14
- 使用官方 Python 3.12 `--rm` 容器，未使用 skip、xfail 或 Mock PostgreSQL/基础设施。

# 8. 测试数据与数据库状态

- 专项测试使用外层事务回滚，未使用 TRUNCATE、DROP TABLE 或 downgrade 清理测试数据。
- Chunk 测试数据无残留。
- 最终 Alembic head：`20260818_0002`。
- `document_chunks` 表：已存在。
- `document_chunks` 测试行数：0。
- `documents` 测试行数：0。
- PostgreSQL、Redis、Qdrant、MinIO：全量测试期间均正常。
- 全量测试数据：无残留。

# 9. 未完成内容

- Chunk 字符切分算法（3-3）。
- ChunkService、Chunk API。
- Parser、Embedding、Qdrant、Vector、Retrieval、RAG、Worker、Redis Queue、Agent Runtime。
