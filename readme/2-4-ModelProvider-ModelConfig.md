# 1. 完成内容

- 实现 Model Provider 和 Model Config 两组基础 CRUD API，各 5 条路由。
- 实现请求/响应分离的 Pydantic v2 Schema、请求级 Service dependency 和统一 `/api/v1` 注册。
- 补充 Provider/Config create/update 唯一性、Provider 关系存在性和 provider_id 列表筛选规则。
- 验证 Provider→Config、Config→Agent 关系及当前 PostgreSQL FK 删除约束。
- 使用 Python 3.12 和真实 PostgreSQL 完成专项 API 测试及全量回归。

Model Provider 路由数量：5

Model Config 路由数量：5

# 2. 新增/修改文件

新增：

- `backend/app/api/routes/model_providers.py`
- `backend/app/api/routes/model_configs.py`
- `backend/app/schemas/model_provider.py`
- `backend/app/schemas/model_config.py`
- `backend/tests/api/test_model_providers.py`
- `backend/tests/api/test_model_configs.py`
- `readme/2-4-ModelProvider-ModelConfig.md`

修改：

- `backend/app/api/deps.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/main.py`
- `backend/app/repositories/agent.py`
- `backend/app/repositories/model.py`
- `backend/app/services/model.py`
- `backend/tests/api/conftest.py`

未修改 Model、Migration、Repository 架构、数据库 Schema、Redis、Qdrant、MinIO 或 Docker Compose。

# 3. Model Provider API

- `POST /api/v1/model-providers`：201；重复 name 返回 409。
- `GET /api/v1/model-providers`：200；支持 offset/limit。
- `GET /api/v1/model-providers/{provider_id}`：200/404；UUID path 参数。
- `PATCH /api/v1/model-providers/{provider_id}`：200；部分更新，更新为重复 name 返回 409。
- `DELETE /api/v1/model-providers/{provider_id}`：204；被 ModelConfig 引用时 Service 在删除前检查引用，抛 ConflictError，API 返回 409 并保留 Provider/Config，不执行 DELETE 或级联。

Router 只调用请求级 ModelProviderService，不直接访问 Repository，也不验证 endpoint 或 secret_ref 的真实可用性。

# 4. Model Config API

- `POST /api/v1/model-configs`：201；Provider 不存在返回 404，重复 name 返回 409。
- `GET /api/v1/model-configs`：200；支持 offset/limit/provider_id。
- `GET /api/v1/model-configs/{config_id}`：200/404；UUID path 参数。
- `PATCH /api/v1/model-configs/{config_id}`：200；部分更新，新 Provider 不存在返回 404，重复 name 返回 409。
- `DELETE /api/v1/model-configs/{config_id}`：204；被 Agent 引用时 Service 在删除前检查引用，抛 ConflictError，API 返回 409 并保留 Config/Agent，不执行 DELETE 或解除关系。

provider_id 筛选是否通过：是；Provider A 的结果只包含 A1/A2，不包含 B1

# 5. Pydantic Schema

- Provider：ModelProviderCreate、ModelProviderUpdate、ModelProviderResponse。
- Config：ModelConfigCreate、ModelConfigUpdate、ModelConfigResponse。
- 字段严格对应现有 ORM Model，没有新增数据库字段。
- 请求统一 `ConfigDict(extra="forbid")`，未知字段返回 422。
- Response 继承 ORMResponse，使用 `ConfigDict(from_attributes=True)`。
- PATCH 使用 `model_dump(exclude_unset=True)`，未传字段不会自动覆盖为 None。
- parameters/config 保持普通 dict，不引入 provider-specific 强类型参数。

# 6. Provider / Config 关系规则

- ModelProvider 1:N ModelConfig 保持不变。
- Config create/update 的最终 provider_id 必须对应已存在 Provider，否则 Service 抛 NotFoundError→404。
- Config name 依据现有数据库全局 unique 设计，在 Service create/update 前检查并映射 ConflictError→409。
- Provider name 在 Service create/update 前检查并映射 ConflictError→409。
- provider_id 查询复用现有 ModelConfigRepository.list_by_provider_id。
- Provider 删除使用 ModelConfigRepository.exists_by_provider_id 做存在性检查；Config 删除使用 AgentRepository.exists_by_model_config_id 做存在性检查。Repository 分层架构不变。
- Provider/Config update 提交后 refresh ORM 对象，确保 updated_at 可安全序列化。

# 7. Secret 安全边界

- Provider API 只接受并返回外部 Secret 引用字段 secret_ref。
- Create/Update Schema 不包含 api_key、secret_key、access_token、token 或 password。
- 请求携带明文 api_key 因 extra="forbid" 返回 422。
- 未实现 Secret Manager、Vault、KMS、解密或环境变量解析。
- 测试和报告没有输出或记录任何本地开发凭据。

明文 api_key 是否被 API 拒绝：是，HTTP 422

# 8. API 测试

实际执行：

```text
python -m pytest backend/tests/api/test_model_providers.py backend/tests/api/test_model_configs.py -v
```

结果：

```text
4 passed in 0.85s
```

API 测试数量：4

passed：4

failed：0

skipped：0

测试通过 httpx AsyncClient/ASGITransport 走 HTTP→FastAPI→Service→Repository→真实 PostgreSQL，没有 Mock Service、Repository 或数据库。fixture 使用 UUID 精确追踪并按 Agent→ModelConfig→ModelProvider→User 顺序清理。

# 9. Agent model_config 回归

真实测试完成：创建 Provider→创建 ModelConfig→创建 Agent(model_config_id=该 Config)，返回 201 且 Agent 的 model_config_id 正确。

随后尝试删除被 Agent 引用的 ModelConfig，Service 返回 ConflictError→HTTP 409；测试确认 Config 和 Agent 均仍存在，没有执行删除、级联或解除 Agent 关系。Provider 被 Config 引用时 DELETE 同样返回 409，测试确认 Provider 与 Config 均仍存在。

Agent model_config 引用是否通过：是

# 10. 全量回归测试

Python 实际版本：`Python 3.12.14`

实际执行：

```text
python -m pytest backend/tests -v
```

全量 pytest：`38 passed, 2 warnings in 6.17s`

总测试数：38

passed：38

failed：0

skipped：0

没有使用 skip、xfail 或 Mock 绕过测试。两条 warning 是 2-3.1 已记录的 Qdrant client/server 次版本兼容和不可达负向测试版本探测警告；按任务要求未修改 Qdrant 版本。

OpenAPI 精确包含 9 个当前路径：原 User/Agent、Model Provider/Model Config 四组资源路径及 `/health`，没有新增其他业务 API。

# 11. 最终数据库状态

- PostgreSQL：running/healthy。
- Alembic revision：`20260817_0001 (head)`。
- 业务表数量：11。
- 11 张业务表最终均为 0 行，本次测试数据无残留。
- Redis、Qdrant、MinIO：均 running/healthy；2-4 API 源码未访问或修改这些基础设施。
- Redis 测试键不存在，Qdrant 临时测试 collection 数量为 0；MinIO 生命周期测试确认临时 bucket 已删除。
- 官方 Python 3.12 临时容器已通过 `--rm` 自动删除。

PostgreSQL 是否 healthy：是

Alembic Revision：`20260817_0001 (head)`

业务表数量：11

测试数据是否残留：否

# 12. 未完成内容

- 未实现真实模型调用、Provider Adapter、Model Gateway、LLM Chat、Prompt、SSE 或模型可用性检查。
- 未验证 endpoint、secret_ref 或 parameters 的供应商语义。
- 未实现 Secret Manager、Vault、KMS、API Key 解析或解密。
- 未实现 Conversation、Message 或后续业务 API。
