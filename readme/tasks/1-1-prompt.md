直接复制给 Codex：

```text
请继续开发「企业员工生命健康 Multi-Agent 平台」。

当前项目已有：

- Electron桌面应用
- React + TypeScript前端
- FastAPI后端
- PostgreSQL
- Redis
- Qdrant
- MinIO
- JWT登录认证
- employee/admin双角色
- RBAC用户管理
- 员工端布局
- AI健康助手页面
- DeepSeek API已接入
- Health Supervisor Agent基础框架已完成

现在实现员工端第二个核心页面：

# 健康档案（Health Profile）

目标：

实现员工个人健康数字画像，为后续：

HealthProfileTool

Health Supervisor Agent

Sleep Agent

Risk Agent

提供真实用户上下文数据。

注意：

先检查已有项目结构。

不要重复创建：

- Layout
- Header
- Sidebar
- JWT认证
- 用户模块

优先复用已有组件和接口。


============================

一、前端页面

页面路径：

/employee/profile


对应左侧导航：

健康档案


整体风格：

严格参考已有 AI健康助手页面。

保持：

- 企业健康科技风
- 白色卡片
- 浅绿色强调
- 圆角16px
- #16A34A主题色
- #E8F8EE浅绿色背景


不要设计成普通个人资料页面。

设计理念：

个人健康数字画像。


页面结构：

```

健康档案

我的个人健康画像

---

基础信息卡片

健康指标卡片

健康趋势卡片

健康风险卡片

AI健康摘要卡片

````


============================

二、基础信息模块


卡片标题：

我的基本信息


展示：


姓名

employee001


年龄

28岁


性别

男


身高

175 cm


体重

72 kg


BMI

23.5


要求：

数据不要写死。

先设计接口调用。

如果接口暂无数据：

显示：

暂无数据


不要伪造健康数据。


============================

三、健康指标模块


卡片标题：

当前健康指标


设计四个指标卡片：


1.

BMI

显示：

23.5


标签：

Health Profile


2.

睡眠

显示：

暂无数据


来源：

Wearable


3.

运动

显示：

暂无数据


来源：

Wearable


4.

心率

显示：

暂无数据


来源：

Wearable



每个指标右下角显示数据来源tag。

例如：

Health Profile

Wearable


============================

四、健康趋势模块


卡片标题：

健康趋势


设计三个Tab：

睡眠趋势

运动趋势

心率趋势


第一版：

没有真实数据。


显示：

暂无健康数据

等待健康设备接入


预留后续：

ECharts图表。


============================

五、健康风险模块


卡片标题：

健康风险评估


第一版显示：


暂无风险评估


完成健康数据收集后，
AI将帮助分析潜在健康风险。



后续连接：

Risk Agent


============================

六、AI健康摘要模块


卡片标题：

AI健康摘要


无数据时显示：

完善健康档案后，
AI健康助手可以：

- 分析健康状态
- 制定运动计划
- 提供饮食建议
- 生成健康方案


如果未来有Agent结果：

显示：

AI分析结果

更新时间

来源：

Health Supervisor Agent


============================

七、编辑功能


页面右上增加按钮：

编辑档案


点击后进入编辑模式。


可修改：

年龄

性别

身高

体重


保存按钮：

保存修改


调用：

PUT

/api/v1/health/profile


============================

八、后端数据库设计


检查已有users表。


不要修改users结构。


新增：

health_profiles表


字段：


id

user_id

age

gender

height

weight

created_at

updated_at


关系：

users.id

1 : 1

health_profiles.user_id



============================

九、后端API


新增：


1.

获取当前员工健康档案


GET

/api/v1/health/profile


要求：

必须使用JWT。


流程：


JWT token

↓

获取当前user_id

↓

查询health_profiles

↓

返回当前用户数据



禁止：

通过参数传user_id查询。


防止员工查看其他员工数据。


返回：

```json
{
"user_id":"001",
"age":28,
"gender":"male",
"height":175,
"weight":72,
"BMI":23.5
}
````

2.

更新健康档案

PUT

/api/v1/health/profile

请求：

```json
{
"age":28,
"gender":"male",
"height":175,
"weight":72
}
```

只能修改当前登录用户。

============================

十、为Agent预留接口

设计数据结构：

HealthProfileTool未来调用：

```
JWT user_id

↓

HealthProfileTool

↓

health_profiles

↓

Agent Context

```

不要现在实现Agent调用。

但是代码结构需要方便后续接入。

============================

十一、前后端联调要求

页面加载：

调用：

GET /api/v1/health/profile

展示用户健康档案。

点击保存：

调用：

PUT /api/v1/health/profile

保存成功：

刷新页面数据。

============================

十二、开发要求

完成前检查：

1.

已有前端目录结构

2.

已有API封装方式

3.

已有数据库ORM模型

4.

已有JWT获取方式

尽量复用已有代码。

不要修改：

* DeepSeek调用
* Agent逻辑
* AI健康助手页面
* 用户管理
* RBAC

============================

完成后告诉我：

1. 修改了哪些文件

2. 新增了哪些数据库模型

3. 健康档案页面结构

4. API接口设计

5. JWT如何保证只能访问自己的健康数据

6. 后续HealthProfileTool如何接入Supervisor Agent

```
```
