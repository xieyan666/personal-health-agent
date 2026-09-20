# 4-7 Multi-Agent

## 当前实现

- 新增 `MultiAgentExecutionContext`，包含 root/current agent、depth、handoff_count、visited_agents 与 parent_run_id。
- 新增 `MultiAgentOrchestrator`，从 `Agent.config.multi_agent` 读取白名单，校验 self-reference、active 状态、模型配置，并将子 Agent 暴露为 `agent__<safe_agent_code>` ToolDefinition。
- 子 Agent 通过现有 Runtime 的 RAG、Tool/MCP 定义与 Chat Provider 能力执行，不新增数据库表或 Migration。
- `AgentRuntimeService` 已接入 Coordinator 的子 Agent ToolDefinition；未启用 Multi-Agent 的 Agent 行为保持不变。

## 验证结果

- 既有 Runtime/Tool 回归：`13 passed`。
- 全量回归（Python 3.12 容器）：`167 passed / 0 failed / 0 errors / 0 skipped`。
- Alembic head：`20260818_0002`。
- 未新增 Schema/Migration。

## 尚未封板项

本轮尚未完成任务要求的完整 4-7 验收：

- 尚未创建并执行 Multi-Agent 专项测试文件。
- 尚未完成 SSE `agent_call_started` / `agent_call_completed` 事件实现与验证。
- 尚未完成 Sub-Agent Built-in Tool、RAG、MCP 的端到端自动化覆盖。
- 尚未执行真实 DeepSeek Multi-Agent 与真实 SSE Multi-Agent 联调。
- 尚未进行本阶段专属临时资源与 child AgentRun 的完整审计验证。

因此当前不能写入“4-7 Multi-Agent 最终验收完成，可封板”。

## 本轮继续验证

- Fake Provider / Runtime / MCP 回归：`45 passed`。
- 全量回归（Python 3.12）：`167 passed / 0 failed / 0 errors / 0 skipped`。
- 已增加 Fake Provider 对 `agent__*` 工具调用的确定性支持，并在 SSE 中输出脱敏的 `agent_call_started` / `agent_call_completed` 事件。

当前仍存在明确结构性阻塞：现有 `AgentRuntimeService` 尚未为子 Agent 创建可审计 child AgentRun，且尚未具备本阶段要求的专属真实 DeepSeek Multi-Agent 测试数据/联调脚本。因此不能声称 4-7 完整验收通过。

## 本轮补充

- Sub-Agent 执行现在创建 child `AgentRun`，复用主 Conversation、`parent_run_id` 运行时关联，并按 pending → running → succeeded/failed 收敛；不创建中间 Message。
- child Run 失败时写入脱敏错误信息，避免 running 残留。
- 既有 Runtime/Tool 回归：`13 passed`；全量：`167 passed / 0 failed / 0 errors / 0 skipped`。

仍未完成本阶段专属专项测试、Sub-Agent RAG/Built-in/MCP 端到端覆盖及真实 DeepSeek Multi-Agent/SSE 联调，故尚不能封板。

当前继续验收时确认的结构性问题：Sub-Agent 执行虽已创建 child AgentRun，但 Coordinator 的 token usage 尚未汇总 child 用量，且嵌套 Sub-Agent 的 ExecutionContext 未完整向下一层传播；在补齐这些边界前不应进行真实 Multi-Agent 封板。

## 最新结构修复与回归

- child usage 已汇总到 root Run，child 保留自身 usage，避免重复累计。
- nested Context 已传播 root_agent_id、current_agent_id、depth、全局 handoff_count、visited_agents 与逐层 parent_run_id。
- Multi-Agent 结构专项：`7 passed / 0 failed / 0 errors / 0 skipped`。
- 全量回归：`174 passed / 0 failed / 0 errors / 0 skipped`。

专项目前仍属于结构边界验证；Sub-Agent RAG/Built-in/MCP 的真实 PostgreSQL 端到端链路，以及真实 DeepSeek Multi-Agent/SSE 联调尚未完成，因此不能封板。

## 最新验收结果

- Multi-Agent 专项：`7 passed / 0 failed / 0 errors / 0 skipped`。
- Agent/Tool/MCP/API 相关回归：`95 passed / 0 failed / 0 errors / 0 skipped`。
- 全量回归：`174 passed / 0 failed / 0 errors / 0 skipped`。

本轮未执行真实 DeepSeek Multi-Agent 或真实 SSE 联调；当前新增专项仍为 Context/边界结构测试，尚未覆盖要求的真实 PostgreSQL Sub-Agent Built-in Tool、RAG、MCP 端到端链路，因此不能写入最终封板结论。

## 端到端阻塞

尝试按现有设计创建 child AgentRun 时，`AgentRunService.create_agent_run()` 会校验 `conversation.agent_id == child_agent.id`。当前设计要求 child Run 复用 Coordinator 的主 Conversation，因此该校验会在 child Run 创建阶段拒绝执行。若改为新建 Conversation，则违反“不创建用户可见 Sub-Agent Conversation”；若放宽校验，则需要明确内部执行模式的服务层边界。该冲突是当前端到端验收的结构性阻塞，未进行真实 DeepSeek 联调。

## Internal child execution 修复

- 新增仅供服务层调用的 `AgentRunService.create_child_agent_run()`；普通 `create_agent_run()` 保持 Conversation 与 Agent 严格绑定。
- 内部 child Run 仅在 root Conversation、parent Run、Coordinator 白名单、child active 状态均合法时允许跨 Agent 复用 Conversation。
- child Run 语义：`agent_id` 表示实际执行的 Sub-Agent，`conversation_id` 表示根 Coordinator 用户会话；不创建 child Message。
- 服务专项（真实 PostgreSQL）：`4 passed / 0 failed / 0 errors / 0 skipped`。
- 全量回归：`175 passed / 0 failed / 0 errors / 0 skipped`。

尚未完成 Sub-Agent Built-in/RAG/MCP 真实端到端与真实 DeepSeek Multi-Agent/SSE 联调，故不能封板。

## 端到端增量验证

- Built-in Tool Sub-Agent（真实 PostgreSQL）：通过；主会话仅保留 User 与最终 Coordinator Assistant，child Run 复用主 Conversation 并成功完成。
- stdio MCP Sub-Agent（真实 PostgreSQL + stdio MCP server）：通过；`add_numbers` 返回 42，child Run succeeded，未写入内部 Message。
- 端到端专项：`2 passed / 0 failed / 0 errors / 0 skipped`。
- 最终全量回归：`176 passed / 0 failed / 0 errors / 0 skipped`。此前一次全量中的 API 连接失败单测重跑通过，随后全量复跑全绿。

RAG Sub-Agent 的真实 PostgreSQL+Qdrant 专项、真实 DeepSeek Multi-Agent 与真实 SSE Multi-Agent 仍未执行，不能封板。

## RAG Sub-Agent 与最终回归状态

- RAG Sub-Agent（真实 PostgreSQL + Qdrant）专项通过：检索索引与 child Run 成功，主 Conversation 仅保留 User/Final Assistant。
- Built-in、stdio MCP、RAG 子 Agent 真实端到端专项均通过。
- 全量回归出现新的基础设施不稳定：`backend/tests/core/test_qdrant.py::test_qdrant_collection_vector_lifecycle` 在全量中 `check_qdrant_connection()` 返回 false；该测试单独执行通过。两次全量均复现该顺序相关的 Qdrant 连接失败，当前全量结果为 `175 passed / 1 failed`。

由于全量未满足 0 failed，且真实 DeepSeek Multi-Agent/SSE 尚未执行，4-7 不能封板。

## 最终验收（2026-08-21）

### Qdrant 顺序问题修复

- 根因：`backend/app/core/qdrant.py` 在模块加载时创建了全局 `AsyncQdrantClient`。前序 `test_sub_agent_rag_uses_real_postgres_and_qdrant` 在其 pytest-asyncio 函数级事件循环中使用该客户端；循环关闭后，`test_qdrant_collection_vector_lifecycle` 复用同一 HTTP transport，触发 `RuntimeError: Event loop is closed`，健康检查因而返回 `false`。
- 最小复现：`backend/tests/agent/test_multi_agent_rag.py` 先于 `backend/tests/core/test_qdrant.py::test_qdrant_collection_vector_lifecycle` 执行，修复前稳定复现，记为 `PRECEDING_TEST=test_sub_agent_rag_uses_real_postgres_and_qdrant`、`QDRANT_FAILURE_REPRODUCED=true`。
- 最小修复：Qdrant client 改为按当前活动事件循环延迟创建；检测到循环切换时重建客户端。`close_qdrant()` 同时清空缓存引用。未添加测试专用逻辑、睡眠或重试。
- 复现组合修复后：`2 passed`；core/services/RAG 回归：`30 passed / 0 failed / 0 errors / 0 skipped`。

### Multi-Agent 真实 DeepSeek 联调

- 通过一次性、自动清理的 Docker Python 3.12 脚本完成真实非流式和 SSE 链路；`DEEPSEEK_API_KEY` 仅确认 `exists`，未输出任何值。
- 非流式：Coordinator 真实发起 `agent__*` 调用；child `AgentRun` 复用 root Conversation；stdio MCP `add_numbers` 实际执行并返回 `42`；child/root Run 均为 `succeeded`；最终 Assistant 单次落库，`output_message_id` 正确；root usage 包含 child usage。
- SSE：已收到 `run_started`、`agent_call_started`、`agent_call_completed`、`message_delta` 与 `run_completed`；child/root Run 均为 `succeeded`；最终 Assistant 单次落库。SSE 事件没有输出 task 全文、child result、RAG Context、MCP arguments/result 或 secret。
- 流式 root usage 已按非流式规则汇总 child usage，避免遗漏 child 计量。
- 一次性脚本已在成功后删除。

### 回归与资源审计

- 连续全量回归（官方 `python:3.12-slim`）：第一次 `176 passed / 0 failed / 0 errors / 0 skipped`；第二次 `176 passed / 0 failed / 0 errors / 0 skipped`。
- 真实联调后的最终全量：`176 passed / 0 failed / 0 errors / 0 skipped`。
- Alembic：`20260818_0002 (head)`。
- 资源审计：PostgreSQL `multi-agent-47-*` / `deepseek-multi-agent-47-*` residual=`0`；Qdrant residual=`0`；root/child running residual=`0`；MCP child-process residual=`0`；Sub-Agent 中间 Message residual=`0`。
- 基础设施：PostgreSQL、Redis、Qdrant、MinIO 健康检查均为 `true`。
- 未新增 Schema 或 Migration；未新增 `parent_run_id` 数据库字段；未创建 Sub-Agent Conversation；未实现 Workflow 或长期 Memory。

“4-7 Multi-Agent 最终验收完成，可封板。”
