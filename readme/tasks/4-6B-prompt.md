任务：4-6B MCP 接入 Tool Registry / Runtime / SSE

项目：
D:\Personal Health Agent

当前已完成：

- 4-6A MCP Client + stdio 基础已封板
- 官方 MCP SDK：mcp 1.29.0
- McpClient.list_tools() / call_tool() 已实现
- stdio transport 已真实跑通
- add_numbers(2,3)=5 已真实验证
- Secret Resolver / stdio command 安全边界已完成
- MCP 专项：21 passed / 0 failed / 0 errors / 0 skipped
- 全量：148 passed / 0 failed / 0 errors / 0 skipped
- Alembic head = 20260818_0002
- PostgreSQL / Redis / Qdrant / MinIO healthy
- 未修改 Schema / Migration
- 当前还未接入 Agent Runtime / ToolRegistry / ToolExecutor / SSE
- HTTP MCP、RAG+MCP、Multi-Agent 尚未实现

本阶段只做：

MCP Tool
→ Tool Registry / ToolExecutor
→ Agent Runtime
→ 非流式 /run
→ SSE /stream

同时要求：

- Built-in Tool + MCP Tool 共存
- 复用 4-5 Tool Loop
- 复用 4-5A Token Budget
- 不实现 HTTP MCP
- 不做 RAG + MCP
- 不做真实 DeepSeek + MCP
- 不进入 Multi-Agent

这些留到 4-6C / 4-6D。

==================================================
一、先读源码
==================================================

优先读取：

backend/app/mcp/
backend/app/tools/
backend/app/agent/runtime.py
backend/app/model_gateway/chat.py
backend/app/models/tool.py
backend/app/services/tool.py
backend/app/repositories/tool.py
backend/app/api/routes/agent_runtime.py
backend/tests/tools/
backend/tests/agent/
backend/tests/api/
backend/tests/mcp/

以及：

readme/4-5-Tool-Calling.md
readme/4-5A-ModelConfig-Token-Budget规范化.md
readme/4-6A-MCP-Client-stdio基础.md

参考源码：

references/langflow-main
只研究：
- MCP Tool 与 Component/Tool Registry 的集成
- Agent Runtime Tool execution
- MCP session/tool invocation
- Streaming Tool event

references/dify
只研究：
- Agent MCP Tool 授权
- Tool metadata → LLM ToolDefinition
- Tool execution result 回填

不要研究：
- Multi-Agent
- Workflow
- HTTP MCP
- RAGFlow

==================================================
二、总体原则
==================================================

不要建立第二套 MCP Tool Loop。

继续复用 4-5 主链路：

AgentRuntimeService
→ ToolDefinition
→ ChatProvider
→ ToolCall
→ ToolExecutor
→ ToolResult
→ ChatProvider
→ Final Assistant

MCP 只是 ToolExecutor 的一种执行后端。

目标结构：

ToolExecutor
├── Builtin Handler
└── MCP Adapter
     → McpClient
     → stdio MCP Server

要求：

- Runtime 不直接操作 MCP SDK
- Model Gateway 不连接 MCP
- McpClient 不管理 AgentRun
- SSE 不直接由 MCP Client 发出
- Tool authorization 继续由 Runtime / Tool 层负责

==================================================
三、复用 Tool 数据库模型
==================================================

本阶段优先复用现有 Tool Model。

先检查当前 Tool 字段。

MCP Tool 通过现有：

Tool.type
Tool.config

表达。

如果能表达，不改 Schema。

建议语义：

Tool.type = "mcp"

Tool.config：

{
  "server": {
    "transport": "stdio",
    "command": "python",
    "args": ["..."],
    "env": {
      "KEY": "env:KEY"
    }
  },
  "remote_tool_name": "add_numbers"
}

字段命名必须以当前实际 Tool Model / Service 为准。

如果当前 type 有固定枚举：
按现有规则扩展最小合法值。

如果 JSON config 已足够，不新增字段。

只有 JSON config 无法表达时才报告：
MCP_SCHEMA_BLOCKER

不要自行新增 Migration。

==================================================
四、MCP Tool Definition 加载
==================================================

实现 MCP ToolDefinition resolver。

流程：

DB Tool
→ 验证 type=mcp
→ 解析 Tool.config
→ McpClient.list_tools()
→ 找到 remote_tool_name
→ McpRemoteTool
→ ToolDefinition

要求：

- 每个 Agent Run 中，同一 MCP Server list_tools 最多一次
- Run 内内存缓存 discovery 结果
- 不用 Redis
- 不持久化 discovery

错误：

MCP_TOOL_NOT_FOUND
MCP_TOOL_SCHEMA_INVALID
MCP_LIST_TOOLS_FAILED

==================================================
五、MCP Tool 内部命名
==================================================

防止 Built-in 与 MCP Tool 名称冲突。

为 LLM ToolDefinition 生成稳定内部 name：

mcp__<server_alias>__<remote_tool_name>

例如：

mcp__test_server__add_numbers

要求：

- 名称合法
- 稳定
- 可从内部 name 映射回对应 DB Tool
- 不直接依赖 remote_tool_name 做授权

server_alias 从 Tool config 或现有 Tool name 派生。

不要新增数据库字段。

==================================================
六、Tool Registry / Executor 接入
==================================================

扩展现有：

ToolRegistry
ToolExecutor

Builtin 路径保持不变。

MCP Tool：

ToolExecutor
→ McpToolAdapter / Handler
→ McpClient.call_tool()

建议新增：

backend/app/tools/mcp.py

或同级合理位置。

职责：

- 接受已授权 DB Tool
- 解析 config
- 调用 McpClient
- 转成现有 ToolResult

不要让 MCP Adapter：
- 调 ChatProvider
- 写 Message
- 改 AgentRun
- 发 SSE

==================================================
七、Agent.config.tools 保持不变
==================================================

继续使用：

{
  "tools": {
    "enabled": true,
    "tool_ids": [...],
    "max_iterations": 5
  }
}

tool_ids 可以同时包含：

- Built-in Tool ID
- MCP Tool ID

不要新增：

Agent.config.mcp

Runtime 不应通过单独 mcp 开关判断。

==================================================
八、授权逻辑
==================================================

继续沿用 4-5：

Agent.config.tools.tool_ids
→ DB Tool
→ ToolDefinition
→ Provider

模型只能调用当前 Agent 已授权 Tool。

MCP internal name 返回后：

必须映射到已授权 DB Tool。

禁止：

- 只因为 McpClient 能发现 Tool 就允许调用
- 模型通过任意 remote_tool_name 绕过 tool_ids
- 未授权 MCP Tool 被执行

未授权：

TOOL_NOT_AUTHORIZED

==================================================
九、Tool 参数校验
==================================================

MCP Tool 参数 schema 来自：

MCP inputSchema

DeepSeek/Fake 返回 arguments 后：

继续走 4-5 现有安全 JSON parser。

然后按照 MCP ToolDefinition.parameters_schema 校验。

不要直接把未校验参数交给 McpClient。

非法：

MCP_TOOL_ARGUMENTS_INVALID

禁止：
- 自动补参数
- 自动改字段名
- eval
- ast.literal_eval

==================================================
十、非流式 Runtime
==================================================

接入现有：

AgentRuntimeService.run()

流程：

User
→ 加载 Agent tools
→ Built-in + MCP ToolDefinitions
→ Provider
→ ToolCall
→ 授权
→ ToolExecutor
→ MCP call_tool
→ ToolResult
→ 第二轮 Provider
→ Final Assistant

要求：

- Tool内部消息不落库
- Assistant最终只落库一次
- output_message_id正确
- max_iterations继续有效
- usage多轮累加
- latency保持现有语义
- AgentRun succeeded/failed正确

==================================================
十一、Token Budget
==================================================

严格复用 4-5A：

- 默认 max_tokens=1024
- Tool最低预算=256
- Runtime override继续可用
- finish_reason=length：
  → TOOL_CALL_TRUNCATED
  → 不执行 MCP Tool

禁止 MCP 自己设计一套 token budget。

==================================================
十二、SSE Runtime
==================================================

接入现有：

AgentRuntimeService.stream_run()

继续使用已有事件：

run_started
tool_call_started
tool_call_completed
message_delta
run_completed
error

不要新增 mcp_* SSE 事件。

MCP Tool 对客户端表现与 Built-in Tool 一致。

tool_call_started：

仅：
- tool_call_id
- tool_name

tool_call_completed：

仅：
- tool_call_id
- tool_name
- success

禁止 SSE 输出：

- command
- args
- env
- MCP server config
- Tool arguments
- Tool result
- secret
- traceback

==================================================
十三、Streaming Tool Loop
==================================================

继续复用 4-5 Streaming Tool Calling：

Provider stream
→ 聚合 tool_call fragments
→ parse arguments
→ ToolExecutor
→ MCP Tool
→ Tool Result
→ 第二轮 provider stream
→ Final Assistant

要求：

- fragments 完整后才执行
- MCP Tool 只执行一次
- Tool Result 后正常开启第二轮 stream
- Assistant单次落库
- run_completed正常

==================================================
十四、MCP 生命周期
==================================================

MCP Client 在单次调用内：

connect
→ call_tool
→ close

或按 4-6A 已有实现。

本阶段优先正确性，不做长连接池。

必须确保：

- 正常调用 child process 退出
- Tool失败 child process 也退出
- Runtime cancel/exception 不残留 MCP process

==================================================
十五、错误映射
==================================================

复用 4-6A 错误码：

MCP_CONFIG_INVALID
MCP_CREDENTIAL_MISSING
MCP_SERVER_CONNECT_FAILED
MCP_LIST_TOOLS_FAILED
MCP_TOOL_SCHEMA_INVALID
MCP_TOOL_NOT_FOUND
MCP_TOOL_ARGUMENTS_INVALID
MCP_TOOL_EXECUTION_FAILED
MCP_TOOL_EMPTY_RESULT

Runtime规则：

任何 MCP 执行失败：

AgentRun -> failed
不创建最终 Assistant Message

SSE：

error
然后终止。

不得停留 running。

==================================================
十六、Built-in + MCP 共存
==================================================

必须自动化验证一个 Agent 同时授权：

calculate_bmi
+
MCP add_numbers

Provider 可看到两个 ToolDefinition。

Fake Provider 可分别选择：

calculate_bmi
或
mcp__...__add_numbers

验证：

- Built-in 路径不回归
- MCP 路径可执行
- internal name映射正确
- Tool ID授权有效

==================================================
十七、测试 MCP Server
==================================================

继续复用 4-6A：

backend/tests/mcp/fixtures/test_server.py

使用真实 stdio MCP Server：

add_numbers(a,b)

2 + 3 = 5

不要创建新的平行测试协议。

==================================================
十八、Fake Provider MCP Tool Calling
==================================================

扩展 FakeChatProvider / 测试 Fake 行为。

自动化测试不访问真实 DeepSeek。

测试输入可以明确触发 MCP add_numbers：

例如：

“请使用 add_numbers 计算 2 + 3。”

第一轮：

ToolCall
→ MCP internal name
→ arguments {a:2,b:3}

Runtime执行：

MCP Server
→ result=5

第二轮 Fake：

返回最终 Assistant。

==================================================
十九、测试文件
==================================================

新增/补齐：

backend/tests/tools/test_mcp_adapter.py
backend/tests/agent/test_runtime_mcp.py
backend/tests/api/test_agent_mcp.py

必要时扩展：

backend/tests/mcp/
backend/tests/model_gateway/test_chat_tools.py

==================================================
二十、必须覆盖测试
==================================================

A. ToolDefinition resolver

- valid MCP Tool
- list_tools成功
- remote tool存在
- remote tool不存在
- invalid schema
- Run内同一 Server discovery只一次

B. Registry/Executor

- Built-in Tool仍正常
- MCP Tool执行add_numbers
- 2+3=5
- MCP Result -> ToolResult
- MCP execution error安全映射

C. Authorization

- 已授权 MCP Tool可执行
- 未授权拒绝
- remote name不能绕过tool_ids
- Built-in+MCP同时授权正常

D. Runtime非流式

- MCP Tool Loop完整
- Tool内部消息不落库
- Final Assistant单次落库
- output_message_id正确
- usage累加
- max_iterations
- MCP error -> Run failed
- no running residual

E. SSE

事件顺序：

run_started
→ tool_call_started
→ tool_call_completed
→ message_delta>=1
→ run_completed

失败：

run_started
→ ...
→ error

验证：

- MCP child process退出
- Tool只执行一次
- Assistant单次落库
- MCP config不泄露

F. Token Budget

- max_tokens<256 的 MCP Tool Agent拒绝
- finish_reason=length -> TOOL_CALL_TRUNCATED
- MCP Tool不执行

G. API

- /run MCP Agent成功
- /stream MCP Agent成功
- 非 MCP Tool Agent无回归
- 非法 MCP Tool config正确失败

==================================================
二十一、真实 PostgreSQL
==================================================

Runtime/API专项使用真实 PostgreSQL。

为测试创建临时：

Tool(type=mcp)
Agent
User
Conversation

使用唯一前缀：

mcp-46b-*

测试结束精确清理。

不要依赖数据库为空。

==================================================
二十二、自动化测试
==================================================

使用官方：

python:3.12-slim

先执行：

python -m pytest \
backend/tests/mcp \
backend/tests/tools/test_mcp_adapter.py \
backend/tests/agent/test_runtime_mcp.py \
backend/tests/api/test_agent_mcp.py \
-v

要求：

failed=0
errors=0
skipped=0

然后执行 Tool/MCP相关：

python -m pytest \
backend/tests/tools \
backend/tests/model_gateway/test_chat_tools.py \
backend/tests/agent/test_runtime_tools.py \
backend/tests/agent/test_runtime_mcp.py \
backend/tests/api/test_agent_tools.py \
backend/tests/api/test_agent_mcp.py \
-v

要求全部通过。

最后：

python -m pytest backend/tests -v

要求：

failed=0
errors=0
skipped=0

==================================================
二十三、残留检查
==================================================

最终确认：

PostgreSQL mcp-46b-* residual=0
MCP child process residual=0
AgentRun running residual=0

不要删除正式：

- DeepSeek Provider
- DeepSeek ModelConfig
- Built-in Tool
- KnowledgeBase

==================================================
二十四、数据库边界
==================================================

本阶段原则：

不修改 Schema / Migration。

如果 Tool.type / Tool.config 现有结构足够：
直接复用。

如果确实无法表达 MCP Tool：

停止并报告：

MCP_SCHEMA_BLOCKER

不要自行新增 Migration。

Alembic head保持：

20260818_0002

==================================================
二十五、禁止范围
==================================================

本阶段不要实现：

- HTTP MCP
- Streamable HTTP
- RAG + MCP
- 真实 DeepSeek + MCP
- MCP Marketplace
- MCP Server管理平台
- Redis MCP discovery cache
- Multi-Agent
- Workflow
- Agent Handoff
- 前端 MCP管理

这些留给后续阶段。

==================================================
二十六、最终确认
==================================================

4-6B 验收条件：

- MCP Tool可从DB Tool config解析
- MCP list_tools可转ToolDefinition
- internal MCP tool name稳定
- Agent tool_ids授权有效
- ToolRegistry/Executor可执行MCP Tool
- Built-in + MCP共存
- 非流式MCP Tool Loop通过
- SSE MCP Tool Loop通过
- Tool内部消息不落库
- Assistant单次落库
- usage累加正确
- max_iterations有效
- Token Budget复用4-5A
- truncated Tool Call不执行
- MCP异常 -> Run failed
- no running residual
- MCP child process residual=0
- MCP专项0 failed/errors/skipped
- 全量0 failed/errors/skipped
- Alembic head=20260818_0002
- 未改Schema/Migration
- 未实现HTTP MCP
- 未实现RAG+MCP
- 未实现Multi-Agent

==================================================
二十七、报告
==================================================

生成：

readme/4-6B-MCP接入Tool-Runtime-SSE.md

记录：

1. 4-6A复用内容
2. MCP Tool DB config结构
3. MCP ToolDefinition resolver
4. internal name规则
5. discovery run内缓存
6. Registry / Executor接入
7. authorization
8. nonstream Runtime
9. Streaming Runtime
10. SSE事件
11. Built-in + MCP共存
12. Token Budget复用
13. Error mapping
14. child process生命周期
15. 持久化边界
16. MCP专项结果
17. Tool+MCP回归
18. 全量结果
19. PostgreSQL residual
20. MCP child process residual
21. AgentRun running residual
22. Alembic head
23. Schema/Migration是否修改
24. 是否实现HTTP MCP
25. 是否实现RAG+MCP

如果全部完成，写：

“4-6B MCP 接入 Tool Registry / Runtime / SSE 验收完成，可封板。”

完成后停止。

不要继续 4-6C。

只有：
1. 全部完成；
或
2. 出现 MCP_SCHEMA_BLOCKER；
或
3. 出现真实 Runtime 结构性阻塞

时再回复。