# Agent 模块

`backend.app.agent` 仅承载业务 Agent 的定义与编排。所有业务 Agent 必须基于统一 Agent Platform 构建，不得直接调用模型厂商 SDK、数据库、Redis、Qdrant 或未经注册的工具。

## 模块结构

```text
agent/
├── health_supervisor/
│   ├── physical_health/
│   ├── mental_health/
│   ├── sleep_health/
│   ├── exercise_fitness/
│   ├── nutrition_diet/
│   ├── occupational_health/
│   ├── chronic_disease_risk_management/
│   ├── health_habits/
│   ├── health_report_interpretation/
│   └── health_plan/
├── risk_and_safety/
│   ├── physical_health_risk/
│   ├── mental_risk_identification/
│   ├── emergency_event/
│   └── medical_boundary_safety/
└── enterprise_health_services/
    ├── health_service_navigation/
    ├── health_examination_management/
    ├── health_activity_operations/
    └── enterprise_health_qa/
```

## 依赖边界

```text
Business Agent
  -> Agent Runtime
    -> Model Gateway
    -> Tool Registry / MCP
    -> Memory Service
    -> RAG Service
    -> Safety
    -> Observability / Audit
```

风险与安全 Agent 负责业务风险识别和编排，但不可替代平台级强制 Safety Policy。医疗相关输出必须经过风险分类、策略检查、输出安全检查和审计记录；紧急场景必须支持人工升级。

