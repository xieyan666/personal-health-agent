# 3-6 Retrieval / RAG

## 参考设计

参考 RAGFlow 的 Retrieval 工具与 dataset retrieval 调用路径：检索前限定知识库/嵌入模型，向量层只提供候选定位与分数，权威正文由主存储补齐，并跳过单个不合法或过期候选。本项目未复制其混合检索、元数据过滤、重排或生成能力。

## 实现

- `RetrievalService`：query → Fake Embedding → 当前 KnowledgeBase 的 Qdrant Collection → PostgreSQL Chunk 正文。
- `top_k` 默认 5，范围 1–20；空 query 返回 ValidationError。
- Qdrant payload `knowledge_base_id` 不匹配、chunk_id 非法或 PostgreSQL Chunk 不存在时忽略。
- `RagService` 只按检索顺序拼接 `--- chunk {index} ---` Context，不调用 LLM、不生成回答。
- API：`POST /api/v1/knowledge-bases/{id}/retrieve` 与 `/rag-context`。

## 验证

- 专项：Python 3.12.14，4 passed、0 failed、0 skipped。
- 全量：Python 3.12.14，72 passed、0 failed、0 skipped。
- 专项使用真实 PostgreSQL、Qdrant 与 FakeEmbeddingProvider；临时 Qdrant Collection 在 finally 中删除。
- 未修改 Schema/Migration，未实现或调用 LLM、Agent Runtime、Chat 回答生成。
