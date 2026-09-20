# 4-6 MCP 阶段最终验收

## 1. 总体结论

4-6A～4-6D 已完成一致性核对。本阶段复用既有 Tool、Agent.config 与 RAG 结构，未新增 MCP 专属表、字段或 Migration。

## 2. 4-6A～4-6D

- 4-6A：MCP Client 支持 stdio，覆盖 initialize、list_tools、call_tool、异常与关闭。
- 4-6B：MCP Tool 接入 Tool Registry、ToolExecutor、Runtime 与 SSE；使用 `mcp__<server_alias>__<remote_tool_name>` 内部名称，并按 Run 缓存 discovery。
- 4-6C：支持 Streamable HTTP；URL scheme、DNS/IP、私网、TLS、timeout、credential/header 脱敏边界已测试。
- 4-6D：RAG Context → DeepSeek → MCP Tool → Final Assistant 已完成真实联调；`add_numbers` 结果为 42，非流式、SSE、RAG+MCP 均成功。

## 3. 架构与边界

`AgentRuntime → ToolExecutor → McpToolAdapter → McpClient → stdio/Streamable HTTP transport`。

MCP Session 负责 initialize/list_tools/call_tool 与生命周期；Tool.config 保存服务端配置、remote_tool_name、server_alias；模型只能提供 arguments，不能覆盖 command、args、URL 或 headers。Built-in、stdio MCP、HTTP MCP 可在同一 Agent 中共存，并通过 `Agent.config.tools.tool_ids` 授权。

RAG Retrieval 每 Run 一次，Context 在 Tool Loop 中保留但不写入 Message、AgentRun 或 SSE。

## 4. Token Budget 与错误码

- 默认 `max_tokens=1024`，Tool 最低预算 `256`。
- `finish_reason=length` 导致截断时映射 `TOOL_CALL_TRUNCATED`，不执行 MCP Tool，Run 失败且不创建最终 Assistant。
- MCP 错误码覆盖配置、transport、credential、连接、list、schema、arguments、执行、空结果；HTTP 覆盖 URL、私网、DNS、连接、timeout、TLS；Runtime 使用 `TOOL_NOT_AUTHORIZED` 与 `TOOL_CALL_TRUNCATED`。

## 5. 安全核对

- stdio command/args 仅来自服务端 Tool.config；禁止 shell、cmd、PowerShell、bash/sh 与 `shell=True`。
- HTTP 仅允许 http/https；默认拒绝 localhost/私网，测试需显式 `allow_private_network`；DNS 解析后再次检查地址，未关闭 TLS 验证，存在 timeout。
- secret 仅使用 `env:` 引用；credential/header、MCP config、arguments/result、RAG Context、traceback 不进入 LLM、SSE 或错误消息。

## 6. 依赖与 Schema

- 官方 MCP SDK：`mcp 1.29.0`（requirements 约束 `mcp>=1.0,<2.0`）。
- 未引入 shell 执行库、自制 JSON-RPC 或重复 HTTP MCP 库。
- Alembic head：`20260818_0002`；4-6 未新增 Schema/Migration，继续复用 `Tool`、`Tool.config`、`Tool.tool_type` 与 `Agent.config.tools`。

## 7. 测试结果

- MCP 总专项（stdio、HTTP、Tool Adapter、Runtime、SSE、RAG+MCP、API、安全）：`43 passed / 0 failed / 0 errors / 0 skipped`。
- Tool + MCP 综合回归：`26 passed / 0 failed / 0 errors / 0 skipped`。
- 全量 `python -m pytest backend/tests -q`，官方 Python 3.12 依赖镜像：`167 passed / 0 failed / 0 errors / 0 skipped`。

## 8. 真实能力与持久化边界

依据 4-6D 已记录的真实执行结果：

- DeepSeek + MCP nonstream：成功。
- DeepSeek + MCP SSE：成功。
- DeepSeek + RAG + MCP：成功；`add_numbers=42`。
- AgentRun succeeded；Assistant 单次落库；SSE 事件链正常。
- User/Final Assistant 写入 PostgreSQL；Tool Call/Tool Result 内部消息、MCP discovery metadata、MCP credential、RAG Context 不持久化。

## 9. 残留与基础设施

- PostgreSQL MCP/DeepSeek MCP 前缀 residual：0。
- Qdrant MCP 临时 collection/points：0。
- AgentRun running：0。
- stdio 子进程：0；HTTP 测试服务器：0（测试 finally 清理）。
- PostgreSQL、Redis、Qdrant、MinIO：healthy。

## 10. 未实现范围与下一阶段边界

未实现 Multi-Agent、Planner、Agent Handoff、Workflow、MCP Marketplace、MCP Server 管理后台、完整 OAuth、权限审批流、Redis MCP discovery cache、前端 MCP 管理界面、RAG+MCP 之外的扩展能力。下一阶段为 4-7，当前不进入实现。

“4-6 MCP 阶段最终验收完成，可封板。”
