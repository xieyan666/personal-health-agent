# 3-4 Embedding

## 实现

- 新增 `EmbeddingProvider` 抽象及 `FakeEmbeddingProvider`，使用 SHA-256 派生固定 8 维浮点向量，不联网。
- `EmbeddingService.embed_chunks(document_id, model_config_id)` 读取现有 Document、DocumentChunk、ModelConfig、ModelProvider，按 `chunk_index ASC` 批量生成内存结果。
- 仅接受 `model_type=embedding`、Provider/Config 为 active 的配置；未知 provider_type 返回 ValidationError。
- 返回 `chunk_id`、`document_id`、`chunk_index`、`vector`、`dimension`；校验数量、维度及数值类型。
- 无 Chunk 返回空列表；不存在 Document/ModelConfig 返回 NotFoundError。

## 持久化边界

Embedding 结果不写 PostgreSQL、不写 Qdrant；未新增表、字段或 Migration，也未修改 Chunk 内容。

## 验证

专项命令：`python -m pytest backend/tests/model_gateway/test_embedding.py backend/tests/services/test_embedding_service.py -v`。

全量命令：`python -m pytest backend/tests -v`。

已补充 ModelConfig 不存在、model_type 非 embedding、Provider 非 active、ModelConfig 非 active 的校验测试。Python 3.12.14 容器专项上一轮结果为 3 passed、0 failed、0 skipped；补充测试尚未在容器中重新执行。多 Chunk、数量/顺序、无 Chunk、Provider 数量/维度错误及全量回归仍需继续验证。

本轮补充了多 Chunk 顺序/数量、空 Chunk、Provider 数量错误和维度错误测试。宿主直接执行失败：`Python38 -m pytest` 报 `No module named pytest`，因此未将宿主结果冒充为 Python 3.12 容器结果。

本次临时容器在专项测试后自动删除。全量 pytest、Alembic head、基础设施最终状态及残留检查尚未执行，不能伪造结果。本阶段不实现 3-5 Qdrant 索引及 3-6 Retrieval/RAG。

最终验证完成。Python 3.12.14 专项：6 passed、0 failed、0 skipped；全量：65 passed、0 failed、0 skipped。Alembic head 为 `20260818_0002`，`document_chunks` 表存在且测试残留为 0。PostgreSQL、Redis、Qdrant、MinIO 均 running/healthy。EmbeddingService 仅返回内存向量，未新增 PostgreSQL Embedding 数据、未写入 Qdrant；临时容器使用 `--rm` 自动删除。
