# 5-5 健康风险页面与 Risk Engine

## 实现范围

本阶段在现有 `health_risk` API 和规则评估服务基础上补齐员工端健康风险页面，未新增数据库表、未改变 JWT/RBAC，也未让页面直接调用 DeepSeek。

## 真实复用的后端模块

- API：`backend/app/api/routes/health_risk.py`
- 服务：`backend/app/services/risk_assessment.py`
- 模型：`backend/app/models/risk_assessment.py`
- 数据来源：`health_profiles`、`sleep_records`、`exercise_records`、`heart_rate_records`
- 接口：`GET /api/v1/health/risk`

接口通过 `get_current_user()` 获取当前用户，调用 `assess_user()` 重新计算并持久化睡眠、运动和心率风险，再返回风险类型、等级、描述、建议和来源。当前规则引擎不依赖 LLM；AI Risk Agent 文案区域为前端基于结构化评估的展示，后续如需生成式解释，应接入现有 Supervisor/Agent Runtime，而不是从页面直接请求模型。

## 前端实现

- 页面：`frontend/src/pages/employee/Risk.tsx`
- 样式：`frontend/src/pages/employee/risk.css`
- 路由：`/employee/risk`，注册于 `frontend/src/router/index.tsx`
- 导航入口：复用 `frontend/src/components/layout/Sidebar.tsx` 已有“健康风险”菜单。

页面包含：

1. 健康风险概览：综合评分、当前风险等级、数据覆盖、最近分析时间。
2. 风险评估列表：睡眠、运动、心率（并兼容 BMI 类型）卡片，显示状态、原因、建议和来源。
3. 风险趋势变化：展示风险指数的趋势占位图结构，后续可替换为历史风险接口数据。
4. AI 风险分析：显示需要关注项和行动建议，当前基于规则结果，不直接调用 DeepSeek。
5. 历史风险记录：展示当前评估记录，后续可接历史快照接口。

## 规则与数据边界

当前 `risk_assessment.py` 的规则为：睡眠平均值小于 6 小时为高风险，6～7 小时为需要关注；运动按每日均值折算每周不足 150 分钟为需要关注；静息心率大于 90 为需要关注。BMI 规则已存在于健康档案页面的基础指标判断中，风险历史分数和日期序列尚未形成独立后端接口，标记为 TODO。

## AI 风险分析展示优化（2026-08-25）

`Risk.tsx` 的 AI 风险分析区域已重构为报告式卡片，包含：分析状态与时间、综合健康判断、评分与等级、睡眠风险发现、可能原因、潜在影响、三项可执行建议，以及数据/规则分析链路。

页面展示的数据仍只来自现有 `GET /api/v1/health/risk` 规则结果。为避免误导，页面中的链路明确为：`Health Profile Tool` → `Wearable Tool` → `Risk Engine`；其中“AI Risk Agent → 生成风险解释与建议”标记为 planned。当前前端没有直接调用 DeepSeek，也没有宣称 Risk Agent 已完成实际模型调用。

健康档案页面已移除“健康风险评估”和“AI 健康摘要”，页面职责调整为只展示健康事实、当前指标和趋势；风险解释和建议集中于健康风险页面。

## 阶段性风险趋势（2026-08-25）

“风险趋势变化”已从前端离散占位数据改为后端规则引擎生成的 **近 30 天综合风险评分（阶段性评估）**。该评分不是每日评分，也不由 LLM 生成。

- 新增模型：`backend/app/models/health_risk_score.py`，表名 `health_risk_scores`。
- 新增迁移：`backend/alembic/versions/20260825_0005_health_risk_scores.py`。
- 新增服务：`backend/app/services/health_risk_trend.py`。
- 新增接口：`GET /api/v1/health-risk/trend`，通过 JWT 仅返回当前用户的数据。
- 新增前端请求：`frontend/src/api/healthProfile.ts` 中的 `getHealthRiskTrend()`。

服务读取 `health_profiles`、`sleep_records`、`exercise_records` 和 `heart_rate_records`，把最近 30 天切分成“第 1 周～第 4 周、本周”五个连续阶段。每阶段以 100 分为基准，按睡眠、周运动时长、静息心率与 BMI 的规则扣分，生成 0～100 分和主要影响因素，并持久化到 `health_risk_scores`。

等级映射固定由规则引擎执行：90～100 为“良好”，75～89 为“稳定”，60～74 为“需关注”，低于 60 为“风险较高”。前端 `Risk.tsx` 使用 ECharts 柱状图展示五个阶段；悬浮提示显示日期范围、评分、等级、主要影响因素和 `Health Risk Engine` 数据来源。

## 历史风险记录（2026-08-25）

历史风险记录不再重复展示睡眠、运动、心率的“当前风险评估”。它复用 `health_risk_scores` 中已持久化的阶段性评分，按评估周期结束日期倒序展示：日期、综合风险评分、规则引擎等级、主要关注因素、评估周期和数据来源。

- 接口：`GET /api/v1/health-risk/history`。
- 鉴权：通过 `get_current_user()` 限定为当前 JWT 用户，不能读取其他员工评分。
- 首次没有评分记录时，接口调用规则服务生成当前五个阶段；有记录时只读取结构化历史数据。
- 前端：`Risk.tsx` 使用纵向时间线卡片，`getHealthRiskHistory()` 读取接口数据；“查看详情”只作为未来风险详情/AI Risk Agent 解释页的预留入口，不触发模型调用。

因此数据链路为：`health_profiles / sleep_records / exercise_records / heart_rate_records` → `Health Risk Engine` → `health_risk_scores` → `/api/v1/health-risk/history` → 历史风险记录组件。

## 验证

代码需要在 Docker 后端容器执行 Alembic 迁移后生效：`alembic upgrade head`。迁移完成后，访问健康风险页会请求阶段性趋势接口并生成/刷新当前用户五个阶段的评分记录。前端构建验证结果以本次提交后的 `npm run build` 为准。

## 后续计划（planned）

- 增加风险评估历史快照和风险指数趋势 API。
- 将概览评分从前端展示计算下沉为可审计的后端规则服务。
- 在 Supervisor → Risk Agent 结构中接入 HealthProfileTool、HealthTrendTool，并由 Agent Runtime 统一调用模型生成解释。
