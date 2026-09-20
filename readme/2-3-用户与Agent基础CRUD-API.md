# 1. 完成内容

- 建立单一 FastAPI 应用入口和统一 `/api/v1` 前缀。
- 实现 User、Agent 基础 CRUD API，各 5 条路由。
- 实现请求/响应分离的 Pydantic v2 Schema，支持 SQLAlchemy ORM 响应。
- 实现 Service 异常到 404/409/422/400 的统一 HTTP 映射。
- API 通过请求级 AsyncSession 调用真实 Service、Repository 和 PostgreSQL。
- 实现 offset/limit 参数校验，以及 Agent scope/owner_user_id 基础筛选；当前不支持两者组合，同时传入明确返回 422，不静默忽略参数。
- 使用真实 PostgreSQL 完成 API 集成测试和 Repository/Service/API 回归测试。

User API 路由数量：5

Agent API 路由数量：5

# 2. 新增/修改文件

新增：

- `backend/app/main.py`
- `backend/app/api/deps.py`
- `backend/app/api/errors.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/users.py`
- `backend/app/api/routes/agents.py`
- `backend/app/schemas/common.py`
- `backend/app/schemas/user.py`
- `backend/app/schemas/agent.py`
- `backend/tests/api/__init__.py`
- `backend/tests/api/conftest.py`
- `backend/tests/api/test_users.py`
- `backend/tests/api/test_agents.py`
- `readme/2-3-用户与Agent基础CRUD-API.md`

修改：

- `backend/app/api/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/user.py`
- `backend/app/services/agent.py`
- `backend/requirements.txt`

未修改 Repository、Model、Alembic Migration、Docker Compose、Redis、Qdrant 或 MinIO 源码。

# 3. FastAPI 应用结构

`backend.app.main:app` 是唯一 FastAPI 应用，标题为 `Personal Health Agent API`。应用只注册 User Router、Agent Router 和进程级 `/health`；没有综合基础设施健康检查。

数据库依赖直接复用 `backend.app.core.database.get_db()`。`get_user_service()` 和 `get_agent_service()` 为每个请求使用当前 AsyncSession 创建 Service，没有全局 Service 单例，也没有新建 Engine/sessionmaker。

FastAPI App 是否可正常 import：是

OpenAPI 是否包含 User/Agent 路由：是，共 4 个资源路径、10 个 CRUD operation；另有 `/health`

# 4. Pydantic Schema

- User：`UserCreate`、`UserUpdate`、`UserResponse`。
- Agent：`AgentCreate`、`AgentUpdate`、`AgentResponse`。
- Update 使用 `model_dump(exclude_unset=True)`，未提交字段不会自动写为 None。
- Response 使用 `ConfigDict(from_attributes=True)` 读取 ORM 属性。
- Agent scope 使用 `Literal["system", "personal"]`，Service 校验仍保留。
- UserCreate、UserUpdate 和 UserResponse 均不包含 `password_hash`；客户端通过 create/patch 传入该字段会因 `extra="forbid"` 返回 422。数据库 Model/Repository 字段保留，但公共 CRUD API 不开放该字段。没有 password、加密、登录或认证功能。

password_hash 是否从 Response 排除：是

UserCreate/UserUpdate 是否仍暴露 password_hash：否

# 5. HTTP 错误映射

统一异常 handler 返回简单结构：

```json
{"detail": "具体错误信息"}
```

NotFound -> HTTP：404 Not Found

Conflict -> HTTP：409 Conflict

Validation -> HTTP：422 Unprocessable Entity

未分类 ServiceError -> HTTP：400 Bad Request

Service 层未引入 FastAPI、HTTPException 或 status code。

# 6. User API

- `POST /api/v1/users`：201，调用 UserService.create_user。
- `GET /api/v1/users`：200，支持 offset >= 0、1 <= limit <= 100。
- `GET /api/v1/users/{user_id}`：200/404，UUID path 参数。
- `PATCH /api/v1/users/{user_id}`：200，真正部分更新。
- `DELETE /api/v1/users/{user_id}`：204，空响应体。

已验证重复 username 返回 409、资源不存在返回 404、非法请求体/分页返回 422，所有 User 响应均不含 password_hash。

# 7. Agent API

- `POST /api/v1/agents`：201，调用 AgentService.create_agent。
- `GET /api/v1/agents`：200，支持分页及单独使用 scope 或 owner_user_id 筛选；两者同时传入返回 422，错误为 `scope and owner_user_id cannot be combined`。
- `GET /api/v1/agents/{agent_id}`：200/404，UUID path 参数。
- `PATCH /api/v1/agents/{agent_id}`：200，真正部分更新。
- `DELETE /api/v1/agents/{agent_id}`：204，空响应体。

AgentService 做了 API 直接需要的最小补充：列表调用现有 system/personal/owner Repository 查询；update 校验 code 冲突、最终 scope/owner 状态及最终 model_config 存在性。User/Agent update 在提交后 refresh ORM 对象，确保数据库生成的 updated_at 可安全进入响应。

已验证 code 冲突 409、非法 scope 422、personal 缺 owner 422、owner/model_config 不存在 404、Agent 不存在 404、scope + owner_user_id 联合筛选 422，以及两项 2-2 update 回归规则。

# 8. API 测试

实际执行命令：

```text
python -m pytest backend/tests/api -v
```

当前统一测试基线为官方 Python 3.12 临时容器。测试链路为 HTTP → ASGI FastAPI → Service → Repository → 本地真实 PostgreSQL，没有 Mock Service/Repository/数据库。

首次结果：2 passed、2 failed。失败均为 PATCH 响应序列化 updated_at 时的 SQLAlchemy MissingGreenlet；原因是数据库 onupdate 后属性过期。UserService/AgentService 在 commit 后增加 session.refresh，修复后重新执行通过。

本轮 Python 3.12 完整回归中 API 子集最终结果：

```text
5 passed in 0.78s
```

API 测试用例数量：5

通过数量：5

失败数量：0

PostgreSQL CRUD 是否真实验证通过：是

测试数据使用 UUID 精确追踪，在 finally 中按 Agent → User 顺序删除；未使用 TRUNCATE、DROP TABLE 或 alembic downgrade。

# 9. Repository / Service 回归测试

实际执行命令：

```text
python -m pytest backend/tests/repositories backend/tests/services backend/tests/api -v
```

Repository + Service + API 回归测试结果：`17 passed, 0 failed, 0 skipped in 2.22s`

Python 实际测试版本：`Python 3.12.14`

其中 Repository 6 个、Service 6 个、API 5 个测试全部通过，没有破坏既有数据访问和业务能力，也未通过跳过测试解决问题。

# 10. 最终数据库状态

- PostgreSQL：running/healthy。
- Alembic revision：`20260817_0001 (head)`。
- 业务表数量：11。
- 11 张业务表最终测试数据均为 0 行。
- 官方 Python 临时测试容器已通过 `--rm` 自动删除。
- Redis、Qdrant、MinIO 未被 API 访问或修改，均保持 running/healthy。

PostgreSQL 是否 healthy：是

最终 Alembic Revision：`20260817_0001 (head)`

业务表数量：11

测试数据是否有残留：否

# 11. 未完成内容

- 未实现 JWT、SSO、RBAC、Authorization Header、登录、注册、密码加密、refresh token。
- 未实现 Model Provider、Model Config、Conversation、Message、KnowledgeBase、Document、Tool、AgentRun、Audit API。
- 未实现 Agent Runtime、LLM、SSE、RAG、Embedding、文件上传、Redis Cache、Qdrant 或 MinIO 业务访问。
- owner_user_id 仍由请求显式传入，后续认证阶段再接入 current_user。

是否存在新的遗留问题：否
