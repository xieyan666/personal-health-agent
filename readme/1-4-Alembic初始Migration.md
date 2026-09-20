# 1. 完成内容

- 已在 `backend/` 下建立标准 Alembic 目录和配置。
- Alembic 使用现有 `Base.metadata`，并在读取 metadata 前导入 `backend.app.models`，使 11 个 Model 完成注册。
- 已配置基于 `DATABASE_URL` 的 SQLAlchemy Async Engine Migration 环境，保留 `postgresql+asyncpg://` 异步驱动。
- 已静态实现 `Initial P0 schema`，只包含指定的 11 张业务表。
- 已核对建表、外键依赖和反向删表顺序。
- 未修改任何业务 Model。

# 2. 新增/修改文件

新增：

- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/README`
- `backend/alembic/versions/20260817_0001_initial_p0_schema.py`
- `readme/1-4-Alembic初始Migration.md`

修改：

- `backend/requirements.txt`：增加 `alembic>=1.13,<2.0`。

# 3. Alembic 配置

- `script_location` 指向 `backend/alembic`。
- `env.py` 将项目根目录加入 Python import path，导入 `backend.app.models` 后再设置 `target_metadata = Base.metadata`。
- 数据库地址只从环境变量 `DATABASE_URL` 读取，并校验必须使用 `postgresql+asyncpg://`。
- 在线模式通过 `async_engine_from_config`、`NullPool` 和 `connection.run_sync()` 支持 Alembic 的异步 Engine 执行方式。
- 离线模式同样从 `DATABASE_URL` 读取地址。
- `alembic.ini` 和 Python 源码均未写死用户名、密码、IP 或数据库名。

# 4. Initial Migration

Migration Revision ID：`20260817_0001`

Down Revision：`None`

Migration 文件：`backend/alembic/versions/20260817_0001_initial_p0_schema.py`

建表顺序：

```text
users
model_providers
model_configs
agents
conversations
messages
knowledge_bases
documents
tools
agent_runs
audit_logs
```

`downgrade()` 使用完全相反的删表顺序。

Migration 是否已实际执行：否

PostgreSQL 是否已启动：否

# 5. 11 张表核对结果

| 表 | 核对结果 |
|---|---|
| users | 包含 username 唯一索引；email/password_hash 可空；包含 auth_source、external_user_id 及二者联合唯一约束。 |
| model_providers | 包含 provider 类型、状态、endpoint、secret_ref 和 JSONB config。 |
| model_configs | 正确引用 model_providers；包含模型名称、类型、状态和 JSONB parameters。 |
| agents | owner_user_id 可空；scope/category 均为 VARCHAR；包含 personal Agent owner 约束及版本约束。 |
| conversations | 正确引用 users 和 agents；包含 user_id + updated_at 复合索引。 |
| messages | conversation_id 外键、parent_message_id 自引用外键及 conversation_id + created_at 复合索引均存在。 |
| knowledge_bases | 包含 vector_collection、index_version、embedding_model_config_id、retrieval_config。 |
| documents | 不包含 owner_user_id、vector_collection；所有权通过 knowledge_bases 关联。 |
| tools | implementation_ref 为 NOT NULL；包含风险、审批、schema、config 和 secret_ref 字段。 |
| agent_runs | 包含 trigger/output message、parent run、input/output summary 和 finished_at；不包含 input/output 完整正文列。 |
| audit_logs | 只有 created_at，没有 updated_at；外键没有 ON DELETE CASCADE。 |

未增加 agent_tools、agent_knowledge_bases、agent_versions、document_jobs、tool_calls、health_profiles、workflow、organization 等后续表。

# 6. Migration 关键约束与索引

- 所有关系字段使用显式 ForeignKeyConstraint，创建顺序满足依赖关系。
- UUID、JSONB、INET 和带时区 DateTime 均使用 PostgreSQL/SQLAlchemy 对应类型。
- TimestampMixin 对应的表包含 `created_at`、`updated_at`，类型为带时区时间并带 `now()` server default。
- users 的身份来源联合唯一约束、agents 的 scope/owner/version 检查约束、knowledge_bases 的 owner/name 唯一约束和 index_version 检查约束均已进入 Migration。
- agent_runs 包含 token 与 latency 非负检查约束。
- messages、conversations、audit_logs 的复合索引和各 Model 声明的单列索引均已进入 Migration。
- audit_logs 外键未设置级联删除，避免业务记录删除时连带删除审计记录。

# 7. 静态验证结果

已完成：

- `backend/alembic/env.py`、初始 Migration 和全部 Model Python 文件通过 AST 语法解析，共检查 12 个文件。
- 静态提取确认 `upgrade()` 正好创建 11 张目标业务表，顺序与依赖顺序一致。
- 静态提取确认 `downgrade()` 正好按反向顺序删除这 11 张表。
- 静态检查确认 Migration 不含 `ondelete` 级联配置。
- 静态检查确认 agent_runs 不含名为 `input` 或 `output` 的完整正文列。
- 11 个 Model 均已由 `backend/app/models/__init__.py` 统一导入；`env.py` 在读取 `Base.metadata` 前导入该包。

# 8. 未验证内容

- 运行时 `configure_mappers()`、`Base.metadata.tables`、Alembic heads/history 命令未验证。
- 原因：当前 Python 环境仍缺少 SQLAlchemy，因此 Alembic 和 Model 无法完成运行时 import；按任务要求未再次尝试联网安装。
- 未执行 `alembic current`，因为依赖不可用，且该命令还需要数据库连接状态。
- 未执行 `alembic upgrade` 或 `alembic downgrade`。
- 未启动或连接 PostgreSQL，真实数据库中仍未创建任何表。
- 未验证 PostgreSQL 实际 Migration；留待 1-5 PostgreSQL 启动与 Migration 验证阶段完成。
