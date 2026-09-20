# 3-3 Chunk 切分与 ChunkService

## 实现

- `chunk_size=1000`，`chunk_overlap=200`，`step=800`。
- `split_text()` 使用确定性的字符窗口，保持原文顺序；索引从 0 连续递增，末块可小于 1000。
- 空字符串或纯空白文本返回空列表，不写入数据库。
- `ChunkService` 实现创建、按文档查询和按文档删除；Document 不存在返回 NotFoundError，同一 Document 已有 Chunk 时返回 ConflictError。
- 创建过程由 Service 统一事务提交，任何异常回滚；`char_count` 使用 Python `len()`。
- 新增只读接口 `GET /api/v1/documents/{document_id}/chunks`，响应只包含 document_chunks 现有字段。
- Document 存在 Chunk 时，删除接口返回 HTTP 409，既不删除 Chunk，也不执行 MinIO 删除。

## 范围

本阶段未实现 Parser、Embedding、Qdrant、RAG、Worker 或 Agent Runtime，未修改 document_chunks Schema/Migration。

## 验证

专项命令：`python -m pytest backend/tests/services/test_chunk_service.py backend/tests/api/test_chunks.py -v`。

全量命令：`python -m pytest backend/tests -v`。

已确认官方镜像 Python 版本为 3.12.14，且 `backend/requirements.txt` 在临时容器中安装成功。专项测试真实连接本地 PostgreSQL/MinIO，最终结果为 **5 passed, 0 failed, 0 skipped**。全量回归结果为 **59 passed, 0 failed, 0 skipped**。

最终 Alembic head 为 `20260818_0002`，`document_chunks` 表中测试残留数为 0。Docker Compose 中 PostgreSQL、Redis、Qdrant、MinIO 均为 running/healthy。测试容器已自动删除，未记录任何凭据。

Alembic head 与 PostgreSQL/Redis/Qdrant/MinIO 状态、测试数据残留情况需在 pytest 能完成启动后重新验证。
