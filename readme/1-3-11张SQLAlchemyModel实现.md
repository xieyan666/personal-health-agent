# 1. 完成内容

- 已基于现有 `Base` 和 `TimestampMixin` 实现指定的 11 张 SQLAlchemy 2.x Model。
- 已使用 `Mapped`、`mapped_column` 和 `relationship`，未建立第二套 Declarative Base。
- 已按职责拆分 Model 文件，并在 `backend/app/models/__init__.py` 统一导出。
- 已使用 PostgreSQL UUID、JSONB、INET；时间字段使用带时区 DateTime（PostgreSQL TIMESTAMPTZ）。
- 状态、风险和分类字段均使用 VARCHAR，没有新增 PostgreSQL Native ENUM。
- 未创建 Alembic Migration，未连接或启动 PostgreSQL，未实现 API/Service/Repository。

# 2. 新增/修改文件

新增：

- `backend/app/models/user.py`
- `backend/app/models/model.py`
- `backend/app/models/agent.py`
- `backend/app/models/conversation.py`
- `backend/app/models/knowledge.py`
- `backend/app/models/tool.py`
- `backend/app/models/execution.py`
- `backend/app/models/audit.py`
- `readme/1-3-11张SQLAlchemyModel实现.md`

修改：

- `backend/app/models/__init__.py`

# 3. 11 张 Model 列表

| 表 | Model | 文件 |
|---|---|---|
| users | `User` | `user.py` |
| model_providers | `ModelProvider` | `model.py` |
| model_configs | `ModelConfig` | `model.py` |
| agents | `Agent` | `agent.py` |
| conversations | `Conversation` | `conversation.py` |
| messages | `Message` | `conversation.py` |
| knowledge_bases | `KnowledgeBase` | `knowledge.py` |
| documents | `Document` | `knowledge.py` |
| tools | `Tool` | `tool.py` |
| agent_runs | `AgentRun` | `execution.py` |
| audit_logs | `AuditLog` | `audit.py` |

# 4. 主要 Relationship 和 Constraint

- `User`：`username` 唯一；`email/password_hash` 可空；`(auth_source, external_user_id)` 唯一。
- `ModelProvider 1:N ModelConfig`：`model_configs.provider_id` 外键关联 Provider；Provider 只保存 `secret_ref`。
- `Agent`：`owner_user_id` 可空；scope 使用 system/personal VARCHAR；CheckConstraint 要求 personal Agent 必须有 owner；category 使用 VARCHAR。
- `Conversation 1:N Message`：Message 独立保存；建立 `(conversation_id, created_at)` 索引；Message parent/children 使用自引用关系。
- `KnowledgeBase 1:N Document`：vector collection 与 index version 位于 KnowledgeBase；Document 不包含 owner_user_id 或 vector_collection，所有权经 KnowledgeBase 确定。
- `Tool`：`implementation_ref` 非空；input schema/config 使用 JSONB；密钥只保存 `secret_ref`。
- `AgentRun`：正文通过 trigger/output Message FK 关联，只保存 input/output summary；两个 Message relationship 明确 `foreign_keys`；parent run 使用 `remote_side`。
- `AuditLog`：直接继承 Base，不继承 TimestampMixin；只有 created_at、没有 updated_at；relationship 未配置 cascade delete。

# 5. 验证结果

已完成静态验证：

- 所有 Model 文件 AST/语法解析通过。
- 目标 Model 类数量为 11，`__tablename__` 数量为 11。
- users 包含 auth_source/external_user_id，username 唯一，email/password_hash 可空。
- agents.owner_user_id 可空，包含 scope，category 为 VARCHAR，并存在 personal owner CheckConstraint。
- documents 不包含 owner_user_id 和 vector_collection；knowledge_bases 包含 vector_collection。
- tools 包含非空 implementation_ref。
- agent_runs 不含完整 input/output 字段，包含 output_message_id 和摘要字段。
- trigger/output Message relationship 均显式指定 `foreign_keys`。
- parent_run 自引用显式指定 `remote_side`。
- finished_at 使用 `mapped_column(DateTime(timezone=True))`。
- audit_logs 不含 updated_at、不继承 TimestampMixin、未配置 cascade。

# 6. 未验证内容

- 未执行 Model import、`Base.metadata.tables` 和 `configure_mappers()`。
- 原因：当前 Python 环境仍未安装 SQLAlchemy；按本任务要求没有再次尝试安装依赖。
- 因此 mapper relationship 的运行时配置尚未验证，不能声明不存在 mapper error 或 `AmbiguousForeignKeysError`；代码已通过显式 `foreign_keys` 和 `remote_side` 静态规避。
- 未连接 PostgreSQL、未创建表、未生成或执行 Alembic Migration。
