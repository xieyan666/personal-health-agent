# 4-6D RAG + MCP + 真实 DeepSeek 联调

## 1. 实现范围

- 复用现有 `AgentRuntimeService`、`RagService`、`RetrievalService`、`McpToolAdapter` 与 `ToolExecutor`。
- RAG Context 仅注入模型调用消息；不写入 Message、AgentRun 或 SSE 事件。
- MCP 工具沿用现有 Tool Registry 与 per-run discovery cache；未修改 Schema、Migration 或 Qdrant payload。
- 未实现 Multi-Agent、HTTP MCP 新能力或 4-6E。

## 2. 自动化验证

- RAG + MCP 专项：`2 passed, 0 failed, 0 errors, 0 skipped`。
- MCP/RAG 相关回归：`41 passed, 0 failed, 0 errors, 0 skipped`。
- 全量 `python -m pytest backend/tests -q`（Python 3.12 容器）：`167 passed, 0 failed, 0 errors, 0 skipped`。

## 3. 真实联调条件与结果

- `DEEPSEEK_API_KEY=exists`（仅检查存在性）。
- 容器网络检查：可访问 DeepSeek；真实脚本使用官方 `python:3.12-slim` 与现有项目代码。
- 首次真实脚本运行在初始化阶段发现缺少可复用的 active Fake Embedding ModelConfig；已按现有 ModelProvider/ModelConfig Service 增加“缺失才创建、finally 精确清理”的临时配置逻辑，并增加 stdio MCP Tool 缺失时的临时 Tool 创建逻辑。
- 依赖安装通过一次性 `personal-health-agent-46d-test`（基于 `python:3.12-slim`）镜像复用，避免重复下载。
- 真实联调成功：非流式 MCP、SSE MCP、RAG + MCP 均完成；MCP `add_numbers` 返回 42，Runtime 成功，Assistant 仅一次落库，SSE 收到完整运行事件。

## 4. 清理与基础设施

- 临时脚本包含 finally 清理：Qdrant collection、User/Agent/Conversation/Message/AgentRun、Document/Chunk/KnowledgeBase，以及本轮创建的 Tool、Fake Provider/Config。
- 自动化测试使用 `--rm` 临时容器；未发现 running AgentRun 或 MCP 子进程残留。
- Alembic 目标 head：`20260818_0002`。
- 本任务未新增 Schema/Migration，未写入 Embedding 持久化字段，未实现 Multi-Agent。

## 5. 最终验收结果

- PostgreSQL 前缀残留：0；Qdrant 临时 collection/points：0；AgentRun running：0；MCP 子进程：0。
- 最终全量回归：`167 passed, 0 failed, 0 errors, 0 skipped`（Python 3.12 镜像）。
- Alembic head：`20260818_0002`；PostgreSQL、Redis、Qdrant、MinIO healthy。

“4-6D RAG + MCP + 真实 DeepSeek 联调验收完成，可封板。”
