# 4-3 SSE 流式对话

## 参考设计

- Langflow：流式执行将 token chunk 与最终运行结果分离。
- Dify：SSE 采用显式事件类型，流式 delta 不作为持久化消息。

## 实现

- `ChatStreamEvent`：`delta`、`usage`、`done`、`error` 的统一事件结构。
- Fake Provider：确定性多 delta、usage、done。
- DeepSeek Provider：OpenAI-compatible SSE 解析 `delta.content`、`finish_reason` 与 usage；支持显式 `thinking.type=disabled`。
- `AgentRuntimeService.stream_run`：创建 User Message / AgentRun 后推送 `run_started`、`message_delta`；成功时一次性写 Assistant Message 并完成 Run，异常/取消时终结 Run。
- API：`POST /api/v1/agents/{agent_id}/stream`，使用 `StreamingResponse` 生成 `run_started`、`message_delta`、`run_completed`、`error` SSE 事件。

## 验证

- 官方 Python 3.12.14 临时容器专项：4 passed，0 failed，0 errors，0 skipped。
- 全量 `python -m pytest backend/tests -v`：90 passed，0 failed，0 errors，0 skipped。
- 真实 DeepSeek Streaming Smoke：`DEEPSEEK_API_KEY=exists`；`delta_count=13`，`content_non_empty=true`，`finish_reason=stop`，`usage_present=true`，latency positive。
- 真实 SSE Runtime：`run_started=true`，`message_delta_count=1`，`run_completed=true`，AgentRun succeeded，Assistant Message 成功落库，`output_message_id` 与 token/latency 正常回填。
- Assistant Message 只在流成功结束后一次写入；异常测试确认 Run 进入 failed 且不创建不完整 Assistant Message。取消路径使用 AgentRun 允许的 cancelled 状态，不会永久停留 running。
- 临时 Runtime 数据已清理；PostgreSQL 中 `deepseek-stream-43-*` 残留数量为 0。
- Alembic head：`20260818_0002`；未修改 Schema/Migration。PostgreSQL、Redis、Qdrant、MinIO 均为 healthy。
- SSE 不输出 API Key、secret_ref、reasoning_content 或完整异常堆栈；未实现 RAG、Tool、MCP、Multi-Agent。

**4-3 SSE 流式对话验收完成，可封板。**
