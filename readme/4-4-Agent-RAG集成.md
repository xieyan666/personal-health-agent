# 4-4 Agent + RAG 集成

## 实现

- 复用 `Agent.config` JSONB 中的 `rag` 配置：`enabled`、`knowledge_base_id`、`top_k`、`embedding_model_config_id`。
- `AgentRuntimeService` 在模型调用前调用既有 `RagService.build_context`，将非空 Context 作为运行时 system message 注入；原始 User Message、AgentRun 摘要与数据库均不写入 Context。
- 非流式 `/run` 与 SSE `/stream` 共用该编排逻辑；无检索结果时保持原模型调用行为。
- RAG 异常在已创建 Run 后会进入既有 failed 处理，不创建 Assistant Message；SSE 继续使用既有事件格式。

## 边界

未修改 PostgreSQL Schema、Alembic Migration、Qdrant payload 或 SSE 事件格式；未实现 Tool、MCP、Multi-Agent、Query Rewrite 或 Reranker。

## 专项测试

使用官方 `python:3.12-slim` 临时容器并复用本地 PostgreSQL/Qdrant：

```text
python -m pytest backend/tests/agent/test_runtime_rag.py backend/tests/api/test_agent_rag.py -v
5 passed, 0 failed, 0 errors, 0 skipped
```

覆盖了 RAG 开关、Context 注入与不落库、空结果、RAG 失败状态、SSE 事件及 API 输入校验。

## 全量回归

```text
python -m pytest backend/tests -v
95 collected: 95 passed, 0 failed, 0 skipped (Python 3.12.14)
```

已修复两处测试隔离：唯一 UUID 断言仅检查本测试实体，Repository 分页以测试前基线偏移并限定自身实体。未清空业务表、未放宽业务断言。

DEEPSEEK_API_KEY=exists。4-4 专项 5 passed；全量 95 passed。自动化验证确认 PostgreSQL、Redis、Qdrant、MinIO 测试链路正常，Qdrant 版本仅产生兼容性 warning。测试隔离修复已落地，未清空业务表。

本轮尚未完成真实 DeepSeek + RAG 非流式/SSE 联调及临时 RAG 数据清理核验，因此当前不能宣称最终真实模型验收完成；未修改 Schema/Migration/Qdrant payload，也未实现 4-5。

## 本地真实联调入口

当前 Codex 沙箱无法访问 DeepSeek 外网 API；真实联调已在本地有外网环境通过一次性入口执行并返回 `RESULT=success`。入口脚本已删除。

真实链路复用了 `AgentRuntimeService`、`RagService`、`RetrievalService`、`ChunkService` 与 `QdrantIndexService`：Retrieval 命中仅属于临时 KnowledgeBase 的测试知识，Context 包含 `8731`；非流式 Runtime 与 SSE Runtime 均 succeeded，SSE 收到至少一个 `message_delta`，两种 Assistant 输出均包含 `8731`。RAG-disabled 对照正常结束且未调用检索链路。

本轮 `deepseek-rag-44-final-*` PostgreSQL 临时资源与对应 Qdrant collection/points 已由脚本 finally 清理，residual = 0。Context 未持久化到 Message/AgentRun，也未写入 SSE 事件。未修改 Schema、Migration、Qdrant payload 或 SSE 事件格式；未实现 4-5。

4-4 Agent + RAG 集成最终验收完成，可封板。

最终回归（官方 Python 3.12.14 临时容器）：

```text
backend/tests/agent/test_runtime_rag.py + backend/tests/api/test_agent_rag.py: 5 passed, 0 failed, 0 errors, 0 skipped
backend/tests: 95 passed, 0 failed, 0 errors, 0 skipped
```

Alembic head 保持 `20260818_0002`；PostgreSQL、Redis、Qdrant 与 MinIO 均通过真实基础设施测试。未新增 Schema/Migration，未实现 4-5。
