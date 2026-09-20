# 1. 完成内容

- 已建立框架无关的 Service 基础层、统一业务异常和事务边界。
- 已实现 11 个核心业务 Service，对应现有 11 个业务 Repository/Model 领域。
- 已实现附件要求的存在性、唯一性冲突、scope/owner、父子消息、Run 消息归属和 append-only 审计规则；Agent scope 在 Service 层仅允许 `system`/`personal`。
- 所有写方法成功 commit，任意异常 rollback 后继续抛出。
- 已使用真实 PostgreSQL 执行 6 个 Service 集成测试，最终全部通过。
- Service 测试使用 UUID 精确追踪并按依赖顺序清理自身提交的数据，最终无残留。

# 2. 新增/修改文件

新增 Service：

- `backend/app/services/__init__.py`
- `backend/app/services/base.py`
- `backend/app/services/exceptions.py`
- `backend/app/services/user.py`
- `backend/app/services/model.py`
- `backend/app/services/agent.py`
- `backend/app/services/conversation.py`
- `backend/app/services/knowledge.py`
- `backend/app/services/tool.py`
- `backend/app/services/execution.py`
- `backend/app/services/audit.py`

新增测试：

- `backend/tests/services/__init__.py`
- `backend/tests/services/conftest.py`
- `backend/tests/services/test_services.py`

新增报告：

- `readme/2-2-Service基础层.md`

未修改 Repository、Model、Alembic Migration、PostgreSQL Schema、Redis、Qdrant、MinIO 或 Docker Compose。

# 3. Service 分层设计

Service 负责：

- Repository 返回 None 到 NotFoundError 的转换。
- 创建前唯一性、外键存在性和跨记录归属检查。
- 多 Repository 组合查询。
- 写事务 commit/rollback。
- 返回对应 ORM Model 或 Model 列表。

Service 不依赖 FastAPI、HTTPException、HTTP status、Request、Pydantic API Schema、JWT 或权限系统，也不访问 Redis、Qdrant、MinIO、LLM 或 Agent Runtime。

Service 类数量：11 个业务 Service，另有 1 个 BaseService

# 4. 业务异常设计

四种普通 Python Exception：

- ServiceError：统一基类。
- NotFoundError：引用或目标资源不存在。
- ConflictError：明确业务唯一性冲突。
- ValidationError：跨记录归属或输入业务规则不满足。

业务异常类型：ServiceError、NotFoundError、ConflictError、ValidationError

异常层不依赖 FastAPI，不包含 HTTP status code。未把所有 IntegrityError 粗暴转换为 ConflictError；未预检查到的数据库异常 rollback 后原样抛出。

# 5. Transaction 设计

- BaseService 保存外部传入的 AsyncSession，不创建 Engine 或 Session。
- `_transaction()` 是统一 async context manager。
- with 块正常退出后执行 `await session.commit()`。
- 任意 Exception 时执行 `await session.rollback()`，随后原样 raise。
- Repository 仍只负责 add/flush/execute/delete，没有加入业务规则或 commit。

真实测试证明：

- UserService 创建成功后，新 AsyncSession 可以立即查询该用户，确认 commit。
- AgentService 在写入前直接拒绝非法 scope 并抛出 ValidationError；新 Session 查询不到该 code，确认无半成品且不依赖 PostgreSQL CheckConstraint 执行业务校验。

成功写操作是否 commit：是

失败写操作是否 rollback：是

# 6. 各业务 Service

- UserService：CRUD/list、username 和 external identity 冲突、NotFound 转换。
- ModelProviderService：CRUD/list 和 provider name 冲突。
- ModelConfigService：CRUD/list 和 provider 存在性。
- AgentService：CRUD/list、code 冲突、scope 仅允许 `system`/`personal`；create/update 均根据更新后的最终状态校验 personal owner 必填及 User 存在性，同时校验 model config 存在性。
- ConversationService：CRUD、用户会话列表及 user/agent 存在性。
- MessageService：get/list/create/delete、conversation/parent 存在性及 parent conversation 一致性。
- KnowledgeBaseService：CRUD/list、owner 存在性及 owner+name 冲突；不访问 Qdrant。
- DocumentService：metadata CRUD/list 和 knowledge base 存在性；不访问 MinIO/Qdrant。
- ToolService：CRUD/list、name 和 implementation_ref 冲突；不加载工具/MCP。
- AgentRunService：get/list/create/update，验证 agent、conversation、trigger/output Message、parent run，并校验消息 conversation 归属；不执行 Agent。
- AuditLogService：get/list/create，验证可选 actor/run；无 update/delete。

# 7. 测试覆盖

6 个真实 PostgreSQL 测试用例覆盖：

1. User 正常创建、commit 可见、username/external identity 冲突、NotFound、更新、删除，以及数据库失败 rollback 无半成品。
2. Provider 正常/重复、ModelConfig 正常/缺失 provider、system/personal Agent、create/update 非法 scope、personal Agent 清空 owner、无 owner 的 system Agent 切换 personal，以及 owner/code/model config 错误。
3. Conversation 正常/缺失 user/agent，Message 正常 parent、缺失 conversation、跨 conversation parent。
4. KnowledgeBase 正常/缺失 owner/同 owner 同名，Document 正常/缺失 KB，Tool 正常/name/implementation_ref 冲突。
5. AgentRun 正常/parent，缺失 agent/conversation/trigger/parent，以及跨 conversation trigger。
6. AuditLog 正常、缺失 actor/run，并确认 Service 无 update/delete。

测试清理只删除每个用例记录的 UUID，按 audit → run → message → conversation → document → KB → agent → model config/provider → tool → user 顺序执行；不 TRUNCATE、不 DROP TABLE、不 downgrade。

# 8. 测试结果

首次执行为 3 通过、3 失败；失败原因是 pytest function-scope event loop 与全局 Async Engine 池中旧 asyncpg connection 的 loop 不一致。测试夹具在每个用例完成精确清理并关闭 Session 后增加 `engine.dispose()`，未修改 Service/Repository/Model 业务实现。

修正后实际执行：

```text
python -m pytest backend/tests/services -v
```

最终结果：

```text
6 passed in 0.97s
```

测试用例数量：6

通过数量：6

失败数量：0

2026-08-18 小范围修正：AgentService 已增加 create/update 共用的 scope 与最终 owner 状态校验，并补充 create/update 非法 scope、personal 清空 owner、无 owner 的 system 切换 personal 三类 update 断言。使用自动删除的官方 Python 3.8 临时容器连接本地 PostgreSQL 重新执行完整测试，最终结果为 `6 passed in 1.30s`。测试过程未输出数据库连接密码，报告也不记录明文凭据。

# 9. 最终数据库状态

- PostgreSQL：running/healthy。
- Alembic revision：`20260817_0001`。
- 业务表数量：11。
- 11 张业务表测试数据总残留：0 行。
- Redis、Qdrant、MinIO：均保持 running/healthy，Service 源码没有访问这些基础设施。

PostgreSQL 是否 healthy：是

最终 Alembic Revision：`20260817_0001 (head)`

业务表数量：11

测试数据是否有残留：否

# 10. 未完成内容

- 未实现 FastAPI Router、CRUD HTTP API、Pydantic API Schema、JWT、SSO、RBAC、Agent Runtime、Model Gateway、LLM、SSE、RAG、Embedding、Chunk、文件上传、Qdrant 写入、Redis Cache、MCP 或 Workflow。
- Service 当前返回 ORM Model；API Schema 和 HTTP 错误映射留给后续 API 层。
