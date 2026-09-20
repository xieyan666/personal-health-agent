# 4-2 Model Gateway + DeepSeek Provider

## 参考设计

- Langflow：借鉴 Provider 抽象与运行时仅依赖统一模型调用入口的分层方式。
- Dify：借鉴 Provider、ModelConfig 与凭据引用分离的边界；运行记录只保存调用结果，不冗余保存请求内容或凭据。
- DeepSeek 官方 Chat Completions 文档：默认 OpenAI-compatible Base URL 为 `https://api.deepseek.com`，非流式路径为 `POST /chat/completions`。模型名始终读取既有 `ModelConfig.model_name`，没有在代码中固化。

## Chat Provider 与安全边界

- `ChatProvider` 统一返回 `ChatResult`：`content`、`model`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`latency_ms`。
- Provider Factory 注册 `fake` 与 `deepseek`；未知类型直接抛 `ValidationError`，Runtime 不含 Provider 分支判断。
- `FakeChatProvider` 仍为无网络、确定性实现。
- `DeepSeekChatProvider` 只接受 `ModelProvider.secret_ref` 中格式为 `env:VARIABLE` 的引用；当前支持 `env:DEEPSEEK_API_KEY`。缺失、格式非法或环境变量缺失会产生不含密钥的业务错误。
- API Key 不写入 PostgreSQL、不写入 `ModelConfig.parameters`、不写入 API 响应或日志。DeepSeek 错误统一为泛化信息，不包含完整 Key、Authorization header、请求正文或完整敏感请求。
- `ModelConfig.parameters` 仅在存在时向 DeepSeek 传递 `temperature`、`max_tokens`。

## Runtime 集成

- `AgentRuntimeService` 通过 Factory 选择 Provider，并使用 ModelConfig 的 `model_name`、`parameters`。
- 成功时写入 Assistant Message，并将 ChatResult 的 `prompt_tokens`、`completion_tokens`、`latency_ms` 回填既有 AgentRun 字段。
- 非 chat ModelConfig、非 active Provider/Config 均在调用前拒绝；Provider 调用失败将 AgentRun 终结为 `failed`，不创建 Assistant Message，不会停留在 `running`。

## 验证

- 运行环境：官方 `python:3.12-slim` 临时容器，Python 3.12.14，容器使用 `--rm`；宿主机本地基础设施地址仅在容器内映射为 `host.docker.internal`。
- 静态导入：`embedding`、`chat`、`services`、`main` 均通过。
- 专项命令：`python -m pytest backend/tests/model_gateway/test_chat.py backend/tests/agent/test_runtime.py backend/tests/api/test_agent_runtime.py -v`
  - 14 passed，0 failed，0 errors，0 skipped。
- 全量命令：`python -m pytest backend/tests -v`
  - 86 passed，0 failed，0 errors，0 skipped。
  - Qdrant Client/Server 版本差异产生既有 warning，但未影响任何测试结果。
- 真实 DeepSeek smoke test：未执行；当前环境未提供 `DEEPSEEK_API_KEY`。该 smoke test 不纳入日常 pytest，也未发生任何外部模型调用。
- Alembic 基线：`20260818_0002`；版本目录仅包含 `20260817_0001_initial_p0_schema.py` 与 `20260818_0002_document_chunks.py`，本任务未新增或修改 Schema/Migration。
- PostgreSQL、Redis、Qdrant、MinIO：Docker 容器均为 healthy；测试夹具执行精确清理，专项与全量回归完成后无本次测试数据残留。

未实现 SSE、Tool、MCP、RAG 或 Multi-Agent。

**4-2 Model Gateway + DeepSeek Provider 验收完成，可封板。**

## 真实 DeepSeek 联调（4-2B，2026-08-19）

- `DEEPSEEK_API_KEY`：exists（未读取、输出或记录其值）。
- Provider / Factory：复用 `DeepSeekChatProvider` 与现有 ChatProvider Factory，`provider_type=deepseek`、`secret_ref=env:DEEPSEEK_API_KEY`。
- ModelConfig：`model_name=deepseek-v4-flash`、`model_type=chat`、`status=active`；未把 Key 写入 parameters。
- 空内容诊断：首个短请求使用默认 thinking mode，API 成功但最终 `content` 为空。最小修正为 Provider 在参数显式存在时转发官方兼容字段 `thinking`，并脱敏映射 `finish_reason` 与 `reasoning_content_present`；不记录 reasoning 正文。
- Smoke Test：非流式、`thinking.type=disabled`、较小 `max_tokens`，HTTP/API 成功；`content_present=true`、`reasoning_content_present=false`、`finish_reason=stop`、`usage_present=true`、模型为 `deepseek-v4-flash`、`latency_ms>0`。
- Runtime：真实链路成功，`AgentRun=succeeded`、Assistant Message 已落 PostgreSQL、`output_message_id` 正确，`prompt_tokens` / `completion_tokens` / `latency_ms` 已回填。
- 临时数据：曾因一次性清理脚本对象过期产生 `MissingGreenlet`；随后已按精确 `deepseek-42b-*` 前缀核查，残留临时 User 数为 0。正式 DeepSeek Provider / ModelConfig 未删除。
- 自动化回归（官方 Python 3.12.14 临时容器）：专项 14 passed、0 failed、0 errors、0 skipped；全量 86 passed、0 failed、0 errors、0 skipped。Qdrant 版本 warning 未影响结果。

**DeepSeek 真实 API Smoke Test 与 Agent Runtime 联调完成。**
