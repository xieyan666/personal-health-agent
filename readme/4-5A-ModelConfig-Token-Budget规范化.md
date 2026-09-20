# 4-5A ModelConfig Token Budget 规范化

## 1. 背景与参考

4-5 真实 DeepSeek Tool Calling 曾因正式 Chat ModelConfig 的 `max_tokens=32` 返回 `finish_reason=length`，截断 `function.arguments`，形成不完整 JSON。问题不是 Tool parser 兼容性。

参考 Dify 的模型 generation parameters 按模型配置传递方式，以及 Langflow 对通用 `max_tokens` 参数向 Provider 透传、避免过低结构化输出预算的实践；本项目采用单一通用参数入口，而不为 Tool、RAG、未来 MCP 或 Multi-Agent 新增字段。

## 2. Token Budget 与 Context Window

`max_tokens` 是本次生成的输出预算，不是模型 Context Window，也不负责上下文裁剪。它用于避免回答、Tool Call 参数或控制输出在生成中途被截断。

## 3. ModelConfig.parameters 规则

Chat ModelConfig 支持既有 JSON 参数：

```json
{
  "temperature": 0.2,
  "max_tokens": 1024,
  "thinking": {"type": "disabled"}
}
```

- 缺失 `max_tokens`：Runtime 使用默认值 `1024`，不回写历史 JSON。
- 显式值必须为整数，合法范围为 `128`–`8192`；string、float、bool、null 和越界值均拒绝。
- 非 Chat ModelConfig（例如 Embedding）不套用该规则。
- Runtime override 优先级：`override > ModelConfig.parameters.max_tokens > 1024`。

平台推荐值保留为配置建议：router/classifier `256`、Tool `512`、RAG/MCP/planner `1024`、最终回答 `1024`–`2048`；本阶段未新增场景字段或后续模块代码。

## 4. 实现

- `backend/app/model_gateway/chat.py` 提供 `normalize_chat_parameters()`，是 Token Budget 的唯一默认与范围校验来源。
- ModelConfig Service 校验显式 Chat `max_tokens`，但不把缺失默认值写回历史 `parameters`。
- Agent Runtime 的非流式与流式调用均先规范化参数再调用 Provider。
- Tool Agent 的有效预算必须至少为 `256`；更小值抛出 `TOOL_TOKEN_BUDGET_TOO_SMALL`，不会静默提高用户显式配置。

## 5. finish_reason=length 与安全边界

- 普通回答保留 `ChatResult.finish_reason`，已有 content 可继续返回。
- 非流式或流式 Tool Call 在 `finish_reason=length` 时抛出 `TOOL_CALL_TRUNCATED`，不解析、不执行 Tool，AgentRun 失败且不创建最终 Assistant Message。
- 保持严格 parser：不补 `}`、不猜参数、不使用 eval/ast.literal_eval，也不接受 Python dict、数组、标量、null 或自然语言包裹 JSON。

## 6. 正式 DeepSeek 配置更新

通过现有 `ModelConfigService` 更新当前实际使用的正式 DeepSeek Chat ModelConfig；Provider、model_name、secret_ref 和其他参数未改。

```text
model_name=deepseek-v4-flash
old_max_tokens=32
new_max_tokens=1024
thinking=disabled
```

## 7. 测试与真实 Smoke

官方 `python:3.12-slim`：

```text
专项：41 passed, 0 failed, 0 errors, 0 skipped
全量：127 passed, 0 failed, 0 errors, 0 skipped
```

覆盖：默认值与边界、类型拒绝、override、Tool 最低预算、普通 Chat、非流式 Tool 截断、流式 Tool fragments 截断、Tool 不执行与失败后无 Assistant Message。Embedding 配置保持不受影响。

真实 DeepSeek Smoke 使用正式 ModelConfig：普通 Chat 成功且 `finish_reason != length`；`calculate_bmi` Tool Runtime 成功。未输出 API Key、完整 arguments、模型正文或 RAG Context。

## 8. 最终状态

```text
Alembic head: 20260818_0002
PostgreSQL: healthy
Redis: healthy
Qdrant: healthy
MinIO: healthy
Smoke temporary residual: 0
```

未修改数据库 Schema 或 Migration，未实现 MCP 或 Multi-Agent。

4-5A ModelConfig Token Budget 规范化验收完成，可封板。
