# 1. 完成内容

- 已建立从 `DATABASE_URL` 读取 PostgreSQL 异步连接配置的最小配置模块。
- 已建立单一全局 SQLAlchemy Async Engine。
- 已建立统一 `async_sessionmaker` / `AsyncSession` factory。
- 已实现可供依赖注入使用的 `get_db()`；Session 使用结束后关闭，消费过程异常时 rollback 并继续抛出异常。
- 已实现内部 `check_database_connection()`，通过 `SELECT 1` 检查连接。
- 已建立统一 `DeclarativeBase` 和使用带时区时间的 `TimestampMixin`。
- 未创建任何业务 Model、数据表或 Migration。

# 2. 新增文件

- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/models/base.py`
- `backend/requirements.txt`
- `.env.example`
- `readme/1-2-PostgreSQL基础设施实现.md`

# 3. 修改文件

- `backend/app/models/__init__.py`：统一导出 `Base` 和 `TimestampMixin`。

# 4. 数据库连接结构

```text
DATABASE_URL
    ↓
Settings
    ↓
SQLAlchemy Async Engine（全局唯一）
    ↓
async_sessionmaker
    ↓
AsyncSession / get_db()
    ↓
Declarative Base
```

数据库连接检查直接通过 Engine 执行 `SELECT 1`。业务代码后续应使用统一 Session factory 或 `get_db()`，不得自行创建 Engine。

# 5. 环境变量

必填：

```text
DATABASE_URL=postgresql+asyncpg://<username>:<password>@<host>:<port>/<database>
```

Python 代码中没有写死数据库用户名、密码、IP 或 API Key。配置缺失时会明确抛出 `RuntimeError`；driver 不正确时会抛出 `ValueError`。

# 6. 验证结果

已完成：

- 4 个新增/修改 Python 模块的 AST 语法检查通过。
- `DATABASE_URL` 使用 `postgresql+asyncpg://` 时配置读取通过。
- 非 asyncpg PostgreSQL URL 被正确拒绝。
- Backend 业务表声明检查通过：`__tablename__` 数量为 0。
- PostgreSQL 本地端口检查：`127.0.0.1:5432` 关闭。

未完成：

- Python import、SQLAlchemy Base import、Async Engine 实例化、AsyncSession factory 实例化及连接检查函数运行时加载未完成。
- 原因：当前 Python 环境没有安装 `sqlalchemy` 和 `asyncpg`。
- 已尝试执行 `python -m pip install -r backend/requirements.txt`，但代理/网络连接失败，pip 没有找到可下载的发行包；未伪造验证结果。

未验证 PostgreSQL 实际连接。

原因：PostgreSQL 未启动；`127.0.0.1:5432` 端口关闭。同时当前环境缺少运行依赖，且没有配置真实 `DATABASE_URL`。

需要人工验证：网络恢复后安装 `backend/requirements.txt`，设置真实 `DATABASE_URL`，再执行 import/Engine/Session 检查和 `check_database_connection()`。

# 7. 未完成内容

- 未创建 users、agents 等任何业务 Model。
- 未生成或执行 Alembic Migration。
- 未实现 API、登录、Agent、RAG、Redis、Qdrant 或 MinIO。
- 未修改 `docker-compose.yml` 或 `references`。
- 未完成运行时依赖安装与 PostgreSQL 实际连接验证，原因见第 6 节。
