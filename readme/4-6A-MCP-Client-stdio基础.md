# 4-6A MCP Client + stdio 基础

## 1. 范围与参考

本阶段只实现独立 MCP Client、stdio transport、Tool Discovery、`call_tool`、结果规范化和 MCP Tool 到现有 `ToolDefinition` 的基础转换；未接入 Agent Runtime、ToolRegistry、ToolExecutor、SSE、HTTP MCP、RAG 或 Multi-Agent。

参考 Langflow 的 stdio ClientSession 生命周期、初始化与工具发现/调用边界；参考 Dify 的 MCP Tool metadata 与凭据引用边界。未复制大段源码。

## 2. SDK

`backend/requirements.txt` 新增官方 Python `mcp>=1.0,<2.0`。本次 Python 3.12 容器实际安装版本：`mcp 1.29.0`。实际使用当前 SDK 的 `ClientSession`、`StdioServerParameters` 和 `mcp.client.stdio.stdio_client`。

## 3. 模块结构

- `backend/app/mcp/config.py`：stdio 配置解析和环境变量 Secret Resolver。
- `backend/app/mcp/client.py`：独立 `McpClient.list_tools()` / `call_tool()`。
- `backend/app/mcp/types.py`：`McpServerConfig`、`McpRemoteTool`、`McpToolResult` 和 `to_tool_definition()`。
- `backend/app/mcp/errors.py`：稳定 MCP 错误码。

## 4. 配置与安全

配置支持：`transport=stdio`、非空服务端 `command`、`args: list[str]`、`env: dict[str, str]`。环境值统一要求 `env:VARIABLE_NAME`，仅在子进程启动时解析；缺失变量返回 `MCP_CREDENTIAL_MISSING`，不输出值、长度或前后缀。

拒绝 `cmd`、`cmd.exe`、`powershell`、`powershell.exe`、`pwsh`、`bash`、`sh` 及 `&&`、`;`、`|`、换行拼接命令。不使用 `shell=True`，也不允许通过 arguments 覆盖 command。

## 5. stdio 生命周期

每次操作均按：

```text
stdio_client
→ ClientSession
→ initialize
→ list_tools / call_tool
→ close session
→ close transport
```

使用异步 context manager，异常路径也会关闭 session、pipe 与子进程。

## 6. Tool Discovery 与转换

`list_tools()` 调用真实 MCP `tools/list`，返回 `list[McpRemoteTool]`，映射 `name`、`description`、`inputSchema`。name 为空或 inputSchema 非 object JSON Schema 返回 `MCP_TOOL_SCHEMA_INVALID`。

`to_tool_definition()` 只做纯转换：remote name → `ToolDefinition.name`、description → description、inputSchema → parameters；本阶段不做命名空间、冲突处理或 Runtime 授权。

## 7. call_tool 与结果规范化

`call_tool()` 调用真实 MCP `tools/call`，参数必须为 dict。文本 content 按顺序拼接到 `McpToolResult.content`；SDK 提供 `structuredContent` 时写入 `structured_data`。无文本且无 structured result 返回 `MCP_TOOL_EMPTY_RESULT`，不存在 Tool 或执行失败分别映射为安全错误码，不透出 SDK 内部详情。

## 8. 真实测试 Server

`backend/tests/mcp/fixtures/test_server.py` 使用官方 MCP SDK `FastMCP` 启动真实 stdio Server，仅提供 `add_numbers(a, b)`。测试实际启动 Python 子进程，完成 initialize、tools/list、tools/call，`2 + 3 = 5`。

## 9. 测试结果

官方 `python:3.12-slim`：

```text
MCP 专项：21 passed, 0 failed, 0 errors, 0 skipped
全量：148 passed, 0 failed, 0 errors, 0 skipped
```

覆盖配置、Secret Resolver、安全命令拒绝、真实发现、schema、参数传递、执行错误、空结果和 stdio 生命周期。

## 10. 最终确认

```text
MCP child process residual = 0
Alembic head = 20260818_0002
PostgreSQL = healthy
Redis = healthy
Qdrant = healthy
MinIO = healthy
Schema/Migration = 未修改
Agent Runtime = 未接入
HTTP MCP = 未实现
RAG + MCP = 未实现
Multi-Agent = 未实现
```

4-6A MCP Client + stdio 基础验收完成，可封板。
