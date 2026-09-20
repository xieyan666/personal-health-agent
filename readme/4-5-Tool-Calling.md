# 4-5 Tool Calling

4-5 已完成真实 DeepSeek Tool、SSE Tool 与 RAG + Tool 联调，并完成 Python 3.12 自动化回归。

## 步骤级真实联调定位（最新）

官方 `python:3.12-slim` 临时容器已通过真实 DeepSeek 请求复现问题；`indexing`、`retrieval`、Fake Embedding 与 Qdrant 均已通过。步骤级探针将失败定位为：

```text
STAGE=nonstream_runtime
STEP=06_first_provider_request_start
ERROR_TYPE=ValidationError
ERROR_CODE=TOOL_ARGUMENTS_RESPONSE_PARSE_FAILED
RESULT=failure:nonstream_runtime:06_first_provider_request_start:ValidationError
```

根因是首轮 DeepSeek Tool Call 响应中的 `function.arguments` 未能通过现有安全解析契约：仅接受 object、标准 JSON object 字符串或最多两层编码的 JSON object 字符串，且明确拒绝 Python 字面量、数组、标量和空值。失败发生在 Tool 执行、授权、Tool Result 或第二轮请求之前；未输出参数原文、模型正文或任何凭据。现有严格解析策略本身未自动猜测或改写不合规参数，因此需要决定是否允许放宽该安全契约以兼容该模型响应格式；在此之前不应伪造 Tool Calling 成功或封板。

进一步的脱敏结构诊断确认这不是 Markdown/code-fence 或双重编码格式：`arguments` 为长度 18 的字符串，以 `{` 开头、未以 `}` 结尾、无反斜杠、无单引号、无换行，第一次 `json.loads` 即失败；DeepSeek 返回 `finish_reason=length`。根因是首轮 Tool Call 的生成被正式 Chat ModelConfig 的 `max_tokens=32` 截断，产生了不完整 JSON object，而不是解析器缺少一种应接受的格式。

最终联调创建了临时 `deepseek-tool-45-chat-*` Chat ModelConfig，复用正式 DeepSeek Provider 和相同模型名，复制非敏感参数后仅设置 `max_tokens=256`、`thinking.type=disabled`。正式配置未修改；临时 ModelConfig 由 finally 精确删除。真实联调返回 `RESULT=success`：非流式 Tool Loop、SSE Tool Loop 与启用 RAG 的 Tool Loop 均完成。Tool 参数仍使用严格 JSON object 契约，没有自动补全、猜测或改写截断 JSON。

## 本地真实联调入口

一次性脚本 `backend/real_deepseek_tool_45_final.py` 复用现有 Runtime、DeepSeek Provider、Tool Registry/Executor、RagService 与 RetrievalService；使用唯一前缀临时资源并在 finally 清理。它仅输出 `RESULT=success` 或脱敏失败类型。

在有外网的 Windows PowerShell 项目根目录执行：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m backend.real_deepseek_tool_45_final
```

成功后删除脚本，再记录真实结果并封板。

## 容器真实联调结果

官方 `python:3.12-slim` 容器已完成依赖与导入验证（`minio_ok`、`runtime_ok`），并实际运行一次真实联调。结果为 `RESULT=failure:RuntimeError`；脚本 finally 仍执行精确清理。一次性脚本现已增加脱敏阶段标识，供下一次有外网容器运行精确定位 `indexing`、`retrieval`、`nonstream_runtime` 或 `stream_runtime` 阶段，而不输出密钥、请求正文、上下文或 traceback。真实联调未成功，不能封板。

## 已实现基础

- 显式注册的 `ToolRegistry` 和 `ToolExecutor`，不执行数据库中的代码、不使用 eval/exec/shell。
- `ToolDefinition`、`ToolCall`、`ToolResult` 作为 Runtime 与 Provider 的边界对象。
- 内置确定性 `calculate_bmi`：70kg / 175cm 返回 BMI 22.86；参数必须为正数且不允许额外字段。
- `Agent.config.tools` 读取 `enabled`、`tool_ids`、`max_iterations`，并在非流式 Runtime 中执行授权 Tool Loop、累计多轮 usage，内部 Tool 消息不落库。
- Chat Gateway 支持非流式 Tool Call 解析；流式 DeepSeek 按 `index/id/name/arguments fragments` 聚合后才解析 JSON。Runtime 在工具调用前后发出不含参数/结果的 SSE Tool 事件，并将 Tool Result 作为运行时 `tool` message 回填下一轮模型调用。

## 当前验证

官方 Python 3.12 临时容器：

```text
backend/tests/tools + backend/tests/model_gateway/test_chat_tools.py
4 passed, 0 failed, 0 errors, 0 skipped
```

已新增真实 PostgreSQL Runtime 覆盖：Fake Provider BMI Tool Loop、内部 Tool 消息不落库、最终 Assistant 单次落库、output_message_id、流式 Tool 事件顺序与 SSE 脱敏边界；API 保持既有输入校验。

官方 Python 3.12 临时容器最终自动化：

```text
Tool 专项：17 passed, 0 failed, 0 errors, 0 skipped
全量：112 passed, 0 failed, 0 errors, 0 skipped
```

最终残留检查：PostgreSQL residual = 0、Qdrant residual = 0、AgentRun running residual = 0。Alembic head = `20260818_0002`；PostgreSQL、Redis、Qdrant、MinIO 均 healthy。未新增 Schema 或 Migration，未修改 Qdrant payload，未实现 MCP 或 Multi-Agent。一次性真实联调脚本已删除。

4-5 Tool Calling 最终验收完成，可封板。
