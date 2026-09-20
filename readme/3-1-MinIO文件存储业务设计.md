# 1. 完成内容

完成 MinIO 正式文件存储规则、业务 Bucket 初始化、系统 Object Key、FileStorageService、文件类型与大小限制，以及真实 MinIO 专项测试。

- 继续复用 `backend.app.core.minio.get_minio_client()` 返回的单一全局 MinIO Client。
- MinIO 只保存原始文件二进制，不操作 Document 数据库记录。
- 未新增文件 API、Parser、Chunk、Embedding、Qdrant 写入或 RAG。
- 未修改 PostgreSQL Model、Migration、Repository、Redis Client、Qdrant Client 或 Docker Compose。

# 2. 新增/修改文件

新增文件：

- `backend/app/services/file_storage.py`
- `backend/tests/services/test_file_storage.py`
- `readme/3-1-MinIO文件存储业务设计.md`

修改文件：

- `backend/app/core/config.py`
- `backend/app/services/__init__.py`
- `.env.example`
- `.env`（仅增加本地开发 Bucket 名和文件大小上限，不修改或记录现有凭据）

# 3. MinIO 正式 Bucket 设计

- 正式 Bucket：`knowledge-files`。
- 配置项：`MINIO_KNOWLEDGE_BUCKET`，默认值为 `knowledge-files`，Python 业务源码不写死 Bucket 名。
- `ensure_knowledge_bucket()` 和 `FileStorageService.ensure_bucket()` 均提供幂等初始化：不存在时创建，存在时直接返回。
- 全部文件统一存入一个正式 Bucket，不按用户、KnowledgeBase 或 Document 拆分 Bucket。
- Bucket 保持私有；未设置 public/anonymous policy，未生成公开 URL。
- 未启用版本控制、生命周期、归档或自动删除策略。
- 测试不会删除或清空正式 Bucket。

# 4. Object Key 规则

Object Key 格式：

```text
knowledge/{knowledge_base_id}/{document_id}/{uuid_hex}{suffix}
```

例如：

```text
knowledge/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222/0123456789abcdef0123456789abcdef.pdf
```

- KnowledgeBase ID 和 Document ID 必须是 UUID。
- 存储文件名使用新 UUID hex，只保留白名单扩展名。
- 是否使用原始文件名作为 Object Key：否。
- 原始文件名不控制 Bucket、prefix、目录或存储文件名。
- `../../evil.txt` 和 `..\..\evil.txt` 只提取 `.txt`，最终 Key 不含 `..`、反斜杠或 `evil.txt`。
- get/stat/exists/delete 只接受符合系统格式的 knowledge Object Key，拒绝任意路径。
- 两个同名文件通过不同 Document ID 和随机存储 UUID 生成不同 Key。

# 5. 文件类型与大小规则

允许文件类型及 MIME：

- `.txt` → `text/plain`
- `.md` → `text/markdown`
- `.pdf` → `application/pdf`
- `.docx` → `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

主要依据小写化后的扩展名白名单判断，不依赖客户端 Content-Type。`.exe`、`.zip`、`.html` 和无扩展名文件均抛 ValidationError，且不会写入 MinIO。

- 最大文件大小：20 MB。
- 配置项：`MAX_KNOWLEDGE_FILE_SIZE_MB`，默认值 20。
- 字节上限：`20 * 1024 * 1024`。
- 上传前先校验 size；超过上限直接抛 ValidationError，不调用 `put_object()`。
- bytes 输入还会验证声明 size 与实际长度一致。

# 6. FileStorageService

新增独立 `FileStorageService`，仅依赖现有 Settings 和全局 MinIO Client，不访问 SQLAlchemy、Repository、PostgreSQL、Redis 或 Qdrant。

实现能力：

- `ensure_bucket()`：幂等创建/确认正式 Bucket。
- `upload_file()`：校验扩展名和大小、生成 Key、检查冲突、上传并返回 StoredObject。
- `get_file()`：返回 bytes，并始终 close/release MinIO HTTP response。
- `stat_file()`：返回 bucket、object_key、size、content_type、etag。
- `object_exists()`：对象存在返回 True，不存在返回 False。
- `delete_file()`：只删除指定 Object；对象不存在抛 NotFoundError。

操作结果：

- upload：已实现并通过真实 MinIO 验证。
- get：已实现并通过 bytes 一致性验证。
- stat：已实现并验证 size、MIME、Key、etag。
- exists：已实现并验证上传后 True、删除后 False。
- delete：已实现并验证删除成功及重复删除 NotFoundError。

# 7. 安全边界

- 是否允许覆盖：否。目标 Object 已存在时抛 ConflictError，原对象内容保持不变。
- Bucket 是否公开：否。
- 不接受客户端指定 Bucket。
- 不接受完整任意 Object Key 用于上传。
- 不使用原始文件名作为 Object Key。
- 不实现 presigned GET/PUT URL。
- 不批量删除、不递归删除、不删除 Bucket、不按 prefix 清理。
- MinIO SDK 的对象不存在错误转换为 NotFoundError，其他存储异常转换为 ServiceError，不向未来 API 暴露原始 S3Error。
- StoredObject 不包含 Access Key、Secret Key 或连接参数。
- `.env` 凭据未输出、上传或写入本报告。

# 8. MinIO 真实测试

执行命令：

```text
python -m pytest backend/tests/services/test_file_storage.py -v
```

结果：

- 专项测试总数：4
- passed：4
- failed：0
- skipped：0
- Python：3.12.14

测试通过官方 `python:3.12-slim` 自动删除临时容器连接本地真实 MinIO，没有 Mock MinIO、skip 或 xfail。

覆盖：Bucket 幂等、四种合法扩展名、非法扩展名、20MB+1 字节拒绝、Object Key 格式、原始文件名隔离、路径注入、同名文件不冲突、真实 upload/get/stat/exists/delete、禁止覆盖、缺失对象异常和 finally 精确清理。

# 9. 全量回归

执行命令：

```text
python -m pytest backend/tests -v
```

结果：

- Python 实际版本：3.12.14
- 全量 pytest：49 passed，0 failed，0 skipped
- warnings：3（两条既有 Qdrant 版本/不可达探测提示和一条既有 FastAPI 422 常量弃用提示）

全量测试真实连接 PostgreSQL、Redis、Qdrant 和 MinIO；没有通过 skip、xfail 或 Mock 绕过基础设施测试。临时容器均使用 `--rm` 并在结束后自动删除。

# 10. 最终基础设施状态

- PostgreSQL：正常；Alembic `20260817_0001`；11 张业务表共 0 行测试残留。
- Redis：正常；测试键残留 0。
- Qdrant：正常；临时测试 Collection 残留 0。
- MinIO：正常。
- 正式 `knowledge-files` Bucket 是否保留：是。
- 正式 Bucket 最终 Object 数：0。
- 测试 Object 是否有残留：否。
- 临时 `personal-health-test-*` Bucket 残留：0。

# 11. 未完成内容

按 3-1 边界未实现：

- Document 数据库创建、更新、状态或 object_key metadata 入库
- 文件上传、下载或删除 HTTP API
- PDF、DOCX、Markdown、TXT 内容解析
- Chunk Model、Service、API
- Embedding、Qdrant point、索引或检索
- RAG、知识库问答
- Presigned URL、病毒扫描、版本控制、生命周期策略
- 3-2 Document 入库及后续任务
