# 3-5 Qdrant 索引

## 实现

- Collection 选择：由 Document 所属 KnowledgeBase 的 `vector_collection` 决定；不存在时创建，不使用全局 Collection。
- vector_size：使用 Embedding 实际维度，当前 FakeEmbeddingProvider 为 8。
- distance：Cosine。
- Point ID：`DocumentChunk.id` 的字符串形式。
- Payload：仅包含 `chunk_id`、`document_id`、`knowledge_base_id`、`chunk_index`；不包含正文、文件内容或模型配置。
- 幂等：相同 `chunk.id` 重复 upsert 覆盖既有 point，不产生重复。
- 删除：按 payload 的 `document_id` 删除 points，不删除 Collection、PostgreSQL Chunk/Document 或 MinIO Object。
- 未修改 PostgreSQL Schema、未新增 Migration、未新增 Embedding/Vector 字段。

## 测试

新增真实 PostgreSQL + Qdrant 集成测试：`backend/tests/services/test_qdrant_index_service.py`。

- 专项：Python 3.12.14，3 passed、0 failed、0 skipped。
- 全量：Python 3.12.14，68 passed、0 failed、0 skipped。

Qdrant 客户端存在版本兼容 warning（client 1.19.0 / server 1.15.4），不影响本次测试通过。

## 最终检查

- Alembic head：`20260818_0002`。
- `document_chunks` 测试残留：0。
- Qdrant `test_chunks_*` 临时 Collection 残留：0。
- PostgreSQL、Qdrant、Redis、MinIO：均 running/healthy。
- 未实现 3-6 Retrieval / RAG。

## 专项覆盖确认

- 多 Chunk 索引、`indexed_count`、`chunk.id` point ID、白名单 payload、正文不入 payload、KnowledgeBase Collection 选择、Collection 自动创建、8 维 Cosine 配置：已覆盖。
- 重复索引幂等、Document 不存在、无 Chunk 返回 0：已覆盖。
- 已存在 Collection 向量维度不一致返回 ServiceError：已覆盖。
- 仅删除目标 Document points、保留其他 Document points、删除后 PostgreSQL Chunk 仍存在：已覆盖。
