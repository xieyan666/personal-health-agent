# 1. 完成内容

完成 AgentRun 基础 API、Pydantic Schema、关系校验、状态转换、父子 Run、Message 关联、删除保护及真实 PostgreSQL API 测试。

- AgentRun 只作为执行、状态和追踪记录，不执行 Agent 或模型。
- AgentRun 路由数量：5。
- OpenAPI 新增 2 个 AgentRun path、5 个 operation，原有 API 全部保留。
- 未修改 SQLAlchemy Model、Alembic Migration 或数据库 Schema。
- 实际 Model 使用 `user_id`、`trace_id`、`error_code`；不存在 `total_tokens` 和 `error_type`，因此 API 严格采用真实字段，没有虚构字段。

# 2. 新增/修改文件

新增文件：

- `backend/app/api/routes/agent_runs.py`
- `backend/app/schemas/agent_run.py`
- `backend/tests/api/test_agent_runs.py`
- `readme/2-6-AgentRun.md`

修改文件：

- `backend/app/api/deps.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/main.py`
- `backend/app/repositories/execution.py`
- `backend/app/repositories/audit.py`
- `backend/app/services/execution.py`
- `backend/tests/api/conftest.py`
- `backend/tests/services/test_services.py`（既有 AgentRun 测试状态值由旧的 `completed` 对齐为本阶段的 `succeeded`）

# 3. AgentRun API

实现以下 5 条路由：

- `POST /api/v1/agent-runs`
- `GET /api/v1/agent-runs`
- `GET /api/v1/agent-runs/{run_id}`
- `PATCH /api/v1/agent-runs/{run_id}`
- `DELETE /api/v1/agent-runs/{run_id}`

列表支持 `offset`、`limit`、`agent_id`、`conversation_id`、`parent_run_id` 和 `status`。

- `agent_id`、`conversation_id`、`parent_run_id` 最多传一个，同时传多个返回 HTTP 422。
- `status` 可以单独使用，也可以与上述任意一个身份筛选组合，使用 AND 语义。
- 不静默忽略任何筛选参数。
- 列表按 `created_at DESC` 排序。
- `parent_run_id` 只返回直接 Child Run，不递归返回孙 Run。

# 4. Pydantic Schema

新增：

- `AgentRunCreate`
- `AgentRunUpdate`
- `AgentRunResponse`

请求 Schema 使用 `ConfigDict(extra="forbid")`，响应使用 `from_attributes=True`。

创建开放当前 Model 所需的 `user_id`、`agent_id`、`conversation_id`、可选 trigger/parent/model config、status、input summary、risk 和 safety 字段；不开放数据库生成的 id、trace、时间戳或执行完成字段。

PATCH 只允许 status、output message、output summary、error code/message、risk/safety、token 数和 latency；不允许修改运行身份字段或 model config。`prompt_tokens`、`completion_tokens`、`latency_ms` 在 Schema 和 Service 层均要求非负。

Response 只返回 AgentRun 自身字段与关联 ID，不展开 ORM relationship。

# 5. AgentRun 关系规则

- User 不存在：HTTP 404。
- Agent 不存在：HTTP 404。
- Conversation 不存在：HTTP 404。
- Conversation 与 Agent 不一致：HTTP 422。
- Conversation 与 User 不一致：HTTP 422。
- Trigger Message 不存在：HTTP 404。
- Trigger Message 跨 Conversation：HTTP 422。
- Output Message 不存在：HTTP 404。
- Output Message 跨 Conversation：HTTP 422。
- Parent Run 不存在：HTTP 404。
- Parent Run 跨 Conversation：HTTP 422。
- ModelConfig 不存在：HTTP 404。

创建请求不接受 id，因此无法构造当前 Run 对自身的 parent 引用；PATCH 也不开放 parent_run_id。

# 6. 状态与时间规则

支持的 status：

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`

允许的状态转换：

- `pending -> running`
- `pending -> cancelled`
- `running -> succeeded`
- `running -> failed`
- `running -> cancelled`

`succeeded`、`failed`、`cancelled` 是终态，不能回到 pending 或 running。非法状态和非法转换均返回 HTTP 422；Service 层保留独立校验。

- 是否自动设置 started_at：是，首次 `pending -> running` 时设置当前 UTC 时间，已有值不覆盖。
- 是否自动设置 finished_at：是，进入 succeeded/failed/cancelled 时设置当前 UTC 时间，已有值不覆盖。
- 普通 PATCH 不开放 started_at 或 finished_at。
- commit 后执行 `session.refresh()`，响应中的 updated_at、started_at 和 finished_at 可安全序列化。

# 7. 删除冲突规则

- Parent Run 存在 Child Run 时删除 Parent：HTTP 409，Parent 和 Child 均保留。
- AuditLog 引用 AgentRun 时删除 Run：HTTP 409，AgentRun 和 AuditLog 均保留。
- 不级联删除 Child Run 或 AuditLog，也不自动解除 parent_run_id。
- 无引用的 AgentRun 删除成功返回 HTTP 204。

Parent Run 被引用删除是否 409：是。

AuditLog 引用 Run 删除是否 409：是。

# 8. API 测试

执行命令：

```text
python -m pytest backend/tests/api/test_agent_runs.py -v
```

专项测试结果：

- 总数：3
- passed：3
- failed：0
- skipped：0
- Python：3.12.14

测试使用官方 `python:3.12-slim` 自动删除临时容器，通过 HTTP → FastAPI → Service → Repository → 真实 PostgreSQL 执行，没有 Mock Service、Repository 或 PostgreSQL，也没有 skip 或 xfail。

覆盖 CRUD、created_at 降序、身份筛选互斥、status 组合筛选、关系 404/422、状态转换与时间、非负统计字段、Output Message 归属、直接 Child 查询以及两类删除 409。

# 9. 全量回归测试

执行命令：

```text
python -m pytest backend/tests -v
```

结果：

- Python 实际版本：3.12.14
- 总数：45
- passed：45
- failed：0
- skipped：0
- warnings：3

三条 warning 分别为两条既有 Qdrant Client/Server 版本或不可达探测提示，以及 FastAPI/Starlette 对旧 422 常量名称的弃用提示，不影响 HTTP 422 行为和测试结果。

全量测试真实连接 PostgreSQL、Redis、Qdrant 和 MinIO；未使用 skip、xfail 或 Mock 绕过基础设施测试。所有临时测试容器均使用 `--rm`。

# 10. 最终数据库状态

- PostgreSQL 是否 healthy：是。
- Alembic Revision：`20260817_0001`。
- 业务表数量：11。
- 11 张业务表总记录数：0。
- Redis：连接正常，测试键残留 0。
- Qdrant：连接正常，临时测试 Collection 残留 0。
- MinIO：连接正常，临时测试 Bucket 残留 0。
- 测试数据是否残留：否。
- `.env` 中的连接参数和凭据未写入源码、日志或本报告。

# 11. 未完成内容

按任务边界未实现：

- Agent Runtime 或自动执行 Agent
- Model Gateway、OpenAI、Claude 或其他 LLM 调用
- 自动生成 Output Message 或自动推进状态
- SSE、StreamingResponse、WebSocket、chat、events
- Tool Call、MCP、Function Calling
- Worker、后台任务、Celery
- 2-7 及后续功能

AgentRun API 源码只访问 Service、Repository 和 PostgreSQL，没有访问或修改 Redis、Qdrant、MinIO 业务数据。
