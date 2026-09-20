# 4-6C HTTP MCP + 安全边界

## 1. 实现

- 复用 MCP SDK 1.29.0 的 `streamablehttp_client` 与 `ClientSession`，未手写 JSON-RPC。
- `McpServerConfig` 支持 `stdio` 与 `streamable_http`；HTTP 配置使用 `url`、`headers`、`allow_private_network`。
- HTTP 与 stdio 共用 `McpClient.list_tools()`、`call_tool()`、`McpRemoteTool`、`McpToolResult` 和现有 Runtime/ToolExecutor 链路。
- HTTP 请求默认 timeout 30 秒；TLS 使用 SDK 默认证书校验，未关闭验证。

## 2. URL、DNS 与 SSRF

仅允许 `http`/`https`，拒绝其他 scheme、空 hostname、URL 内嵌用户名密码。默认解析 hostname 并拒绝 loopback、私网、link-local、multicast、unspecified、reserved 地址。`allow_private_network=true` 仅用于本地开发/自动化测试，不由 LLM 或请求参数动态开启。

## 3. Header 与凭据

HTTP headers 只来自数据库 Tool.config，值必须使用 `env:NAME` 解析。缺失凭据返回 `MCP_CREDENTIAL_MISSING`；header、token、URL 凭据不进入 ToolDefinition、SSE 或错误消息。Tool arguments 不能覆盖 server URL、headers 或 transport。

## 4. Runtime / SSE

Runtime 不区分 transport；MCP Adapter 继续调用统一 McpClient。HTTP MCP 复用既有非流式与 SSE Tool Loop，事件格式保持 `run_started`、`tool_call_started`、`tool_call_completed`、`message_delta`、`run_completed/error`，不泄露 HTTP 配置、参数或结果。

## 5. 测试

新增真实 FastMCP Streamable HTTP Server fixture，以及 URL/SSRF/header 安全测试、HTTP Client 测试、Runtime/API 测试。官方 Python 3.12.14 临时容器结果：

- `backend/tests/mcp`：32 passed / 0 failed / 0 errors / 0 skipped
- MCP/Runtime/API 专项：38 passed / 0 failed / 0 errors / 0 skipped
- 全量 `backend/tests`：165 passed / 0 failed / 0 errors / 0 skipped

覆盖了 HTTP initialize、tools/list、tools/call、add_numbers(2,3)=5、stdio 回归、私网默认拒绝与测试开关、凭据解析、Runtime Tool Loop、SSE 生命周期。

## 6. 最终状态

- HTTP MCP test server residual：0
- MCP stdio child process residual：0
- PostgreSQL `mcp-46b-*` / `mcp-http-*` residual：0
- AgentRun running residual：0
- Alembic head：`20260818_0002`
- PostgreSQL / Redis / Qdrant / MinIO：healthy
- Schema / Migration：未修改
- RAG+MCP：未实现
- Multi-Agent：未实现
- 真实 DeepSeek + MCP：未执行

4-6C HTTP MCP + 安全边界验收完成，可封板。
