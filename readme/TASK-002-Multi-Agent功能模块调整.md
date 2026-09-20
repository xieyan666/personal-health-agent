# TASK-002 Multi-Agent 功能模块调整

## 1. 任务目标

已完成：将业务功能骨架调整为企业员工生命健康 Multi-Agent 平台，覆盖员工健康总管、风险与安全、企业健康服务、健康数据智能层，并复用已有 Agent Platform。

## 2. 原项目状态

已验证：原项目仅有统一平台层空包，没有具体业务 Agent 和健康数据智能模块。已有 Model Gateway、RAG、Memory、MCP、Tool、Workflow、Safety、Evaluation、Observability 模块可直接保留复用。

## 3. 实现方案

已完成：

- 在 `backend/app/agent/health_supervisor` 下建立 10 个专业健康 Agent 包。
- 在 `backend/app/agent/risk_and_safety` 下建立 4 个风险安全 Agent 包。
- 在 `backend/app/agent/enterprise_health_services` 下建立 4 个企业服务 Agent 包。
- 在 `backend/app/health_data` 下建立 5 个健康数据智能能力包。
- 保留统一 Agent Platform，业务 Agent 后续必须经平台层访问模型、工具、记忆、RAG、安全及可观测能力。

## 4. 修改文件

- `backend/app/agent/__init__.py`

## 5. 新增文件

- `backend/app/agent/health_supervisor/**/__init__.py`
- `backend/app/agent/risk_and_safety/**/__init__.py`
- `backend/app/agent/enterprise_health_services/**/__init__.py`
- `backend/app/health_data/**/__init__.py`
- `readme/TASK-002-Multi-Agent功能模块调整.md`

## 6. 核心代码说明

本任务只建立模块边界，没有加入业务实现。包名采用 Python `snake_case`；包文档说明各模块职责。风险识别、紧急事件与医疗边界 Agent 是业务编排角色，底层强制安全策略仍应统一落在平台级 `safety` 模块，避免安全能力被单个 Agent 绕过。

## 7. API 变化

未完成（不在本任务范围）：无 API 变化。

## 8. 数据库变化

未完成（不在本任务范围）：无 Model、表结构或 Migration 变化。

## 9. 配置项变化

未完成（不在本任务范围）：无配置项变化，`docker-compose.yml` 未修改。

## 10. 测试结果

待实施后填写。

## 11. 未解决问题

未完成：各 Agent、数据引擎和 Supervisor 编排逻辑尚未实现。

未验证：Docker 正在安装，本任务不修改 Compose；安装完成后需单独验证基础设施。

## 12. 后续建议

- 下一步先定义统一 Agent Runtime 接口、调用上下文和路由契约，再逐个实现业务 Agent。
- 优先实现风险分类、策略检查、输出安全检查、审计日志及人工升级闭环。
- 健康数据层应先定义数据所有权、分类、租户隔离和数据来源标记，再接入可穿戴设备数据。
