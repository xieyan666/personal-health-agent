# 4-6B MCP 接入 Tool Registry / Runtime / SSE

## 1. 实现范围

在 4-6A stdio MCP Client 基础上，将数据库 `Tool(tool_type=mcp, config)` 接入现有 Tool Registry/ToolExecutor、Agent Runtime 的非流式与 SSE Tool Loop。未实现 HTTP MCP、RAG+MCP、真实 DeepSeek+MCP 或 Multi-Agent。

## 2. 数据配置与命名

复用现有 `tools` 表，不新增字段、Schema 或 Migration。MCP Tool config 使用 `server`（stdio transport、command、args、env 引用）和 `remote_tool_name`，可选 `server_alias`。发现的远端工具映射为稳定内部名 `mcp__<server_alias>__<remote_tool_name>`，授权仍只接受 Agent.config.tools.tool_ids 中的数据库 Tool。

## 3. Resolver / Executor

Runtime 在单次 Run 内缓存同一 stdio Server 的 `list_tools()` 结果；远端 schema 转为现有 ToolDefinition。新增 McpToolAdapter，仅负责调用 McpClient 并映射为现有 ToolResult；Runtime、Model Gateway、SSE 不直接操作 MCP SDK。Built-in 与 MCP ToolDefinition 可同时提供，MCP 参数继续走现有安全 JSON parser 与 schema 校验。

## 4. Runtime / SSE

非流式链路复用既有 Tool Loop；流式链路复用既有 `run_started → tool_call_started → tool_call_completed → message_delta → run_completed/error` 事件。MCP command、args、env、参数和结果不出现在 SSE；Tool 内部消息不落库，最终 Assistant 仅落库一次，Token Budget 复用 4-5A（默认 1024，Tool 最低 256，截断不执行）。

## 5. 生命周期与错误

每次 MCP 调用由 McpClient 建立 stdio session、调用并关闭，异常映射为既有 MCP 错误码并使 AgentRun failed，不停留 running；正常/异常子进程均由 SDK context manager 回收。

## 6. 测试与验证

新增 `backend/tests/tools/test_mcp_adapter.py`、`backend/tests/agent/test_runtime_mcp.py`、`backend/tests/api/test_agent_mcp.py`，复用 4-6A `test_server.py` 的真实 stdio `add_numbers(a,b)`。测试命令按任务要求使用官方 `python:3.12-slim` 临时容器：

```text
python -m pytest backend/tests/mcp backend/tests/tools/test_mcp_adapter.py backend/tests/agent/test_runtime_mcp.py backend/tests/api/test_agent_mcp.py -v
python -m pytest backend/tests/tools backend/tests/model_gateway/test_chat_tools.py backend/tests/agent/test_runtime_tools.py backend/tests/agent/test_runtime_mcp.py backend/tests/api/test_agent_tools.py backend/tests/api/test_agent_mcp.py -v
python -m pytest backend/tests -v
```

4-6A 基线为 MCP 专项 21 passed、全量 148 passed。本阶段使用官方 `python:3.12-slim` 临时容器完成最终验证：

- MCP/Runtime/API 专项：25 passed / 0 failed / 0 errors / 0 skipped
- Tool+MCP 回归：26 passed / 0 failed / 0 errors / 0 skipped
- 全量：152 passed / 0 failed / 0 errors / 0 skipped
- 实际 Python：3.12.14

## 7. 边界确认

- PostgreSQL Schema/Migration：未修改
- HTTP MCP / Streamable HTTP：未实现
- RAG+MCP / Multi-Agent：未实现
- MCP child process：由 stdio context manager 管理，目标 residual=0

## 8. 最终验收

- PostgreSQL `mcp-46b-*` residual：0
- MCP child process residual：0
- AgentRun running residual：0
- Alembic head：`20260818_0002`
- PostgreSQL / Redis / Qdrant / MinIO：Docker healthcheck healthy
- HTTP MCP：未实现
- RAG+MCP：未实现
- Multi-Agent：未实现

4-6B MCP 接入 Tool Registry / Runtime / SSE 验收完成，可封板。
