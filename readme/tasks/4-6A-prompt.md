任务：4-6A MCP Client + stdio 基础

项目：
D:\Personal Health Agent

当前状态：

- 4-1 Agent Runtime ✅
- 4-2 Model Gateway + DeepSeek ✅
- 4-3 SSE ✅
- 4-4 Agent + RAG ✅
- 4-5 Tool Calling ✅
- 4-5A Token Budget ✅
- 当前全量：127 passed / 0 failed / 0 errors / 0 skipped
- Alembic head = 20260818_0002
- PostgreSQL / Redis / Qdrant / MinIO healthy

本阶段只做：

MCP Client
+ stdio transport
+ Tool Discovery
+ call_tool
+ MCP Tool -> ToolDefinition 基础转换
+ 安全配置解析
+ 自动化测试

本阶段明确不接：

- Agent Runtime
- ToolRegistry / ToolExecutor
- SSE
- HTTP MCP
- RAG + MCP
- DeepSeek + MCP
- Multi-Agent

这些留给 4-6B / 4-6C / 4-6D。

==================================================
一、源码参考
==================================================

开始前先读取当前项目：

backend/app/mcp/
backend/app/tools/
backend/app/models/tool.py
backend/app/services/tool.py
backend/app/model_gateway/chat.py
backend/requirements.txt
backend/tests/

以及：

readme/4-5-Tool-Calling.md
readme/4-5A-ModelConfig-Token-Budget规范化.md

参考源码只研究当前模块：

references/langflow-main

重点：
- MCP Client
- stdio transport
- ClientSession
- list_tools
- call_tool
- session 生命周期
- Tool schema 转换

辅助：

references/dify

只研究：
- MCP Tool metadata
- config / credential 边界
- Tool discovery

不要研究：
- Multi-Agent
- Workflow
- RAGFlow
- HTTP MCP Runtime
- Agent Tool Loop

不要复制大段参考源码。

==================================================
二、先确认 MCP SDK
==================================================

检查 backend/requirements.txt。

如果尚未安装官方 Python MCP SDK：

加入当前可用稳定版本范围。

优先使用官方：

mcp

不要自己实现 JSON-RPC / MCP 协议。

实现前必须实际检查当前安装版本支持的 API。

不要凭记忆使用不存在的：

ClientSession
stdio_client
StdioServerParameters

等接口。

以当前 SDK 实际源码/API 为准。

==================================================
三、MCP 模块结构
==================================================

优先使用现有：

backend/app/mcp/

如果为空，可实现：

backend/app/mcp/
    __init__.py
    client.py
    types.py
    config.py
    errors.py

不要建立与后续 Runtime 强耦合的代码。

4-6A 只提供独立 MCP Client 基础能力。

==================================================
四、核心类型
==================================================

定义清晰内部类型。

例如：

McpServerConfig

至少支持 stdio：

- transport
- command
- args
- env

McpRemoteTool：

- name
- description
- input_schema

McpToolResult：

- success
- content
- structured_data 可选

具体使用 dataclass / Pydantic 按现有项目风格。

不要使用 SDK object 直接穿透到 Runtime 层。

==================================================
五、stdio 配置格式
==================================================

本阶段定义 stdio 配置：

{
  "transport": "stdio",
  "command": "python",
  "args": ["..."],
  "env": {
    "SOME_KEY": "env:SOME_KEY"
  }
}

规则：

transport 必须：

stdio

command：
- 非空字符串
- 只能来自服务端配置
- 不由用户输入动态覆盖

args：
- list[str]
- 不允许嵌套结构

env：
- dict[str, str]
- secret 只能写：
  env:VARIABLE_NAME

禁止明文 credential。

==================================================
六、Secret Resolver
==================================================

实现独立 resolver：

env:SOME_SECRET
→ os.environ["SOME_SECRET"]

要求：

- 只解析 env: 前缀
- 环境变量不存在：
  MCP_CREDENTIAL_MISSING
- 不输出 secret 值
- 不输出长度
- 不输出前后缀

普通非敏感 env 值是否允许直接写入配置：
按当前项目安全风格决定。

如果无法明确区分：
本阶段统一要求 env value 使用 env: 引用。

==================================================
七、stdio 安全限制
==================================================

禁止通过 MCP 配置启动任意 Shell。

明确拒绝 command：

cmd
cmd.exe
powershell
powershell.exe
pwsh
bash
sh

禁止：

shell=True

禁止：

"python xxx.py && rm ..."

这种拼接命令。

必须通过：

command
+
args[]

参数数组方式执行。

不要实现任意代码执行功能。

==================================================
八、MCP Client
==================================================

实现：

McpClient

至少提供：

async list_tools(config)

async call_tool(
    config,
    tool_name,
    arguments
)

内部使用官方 MCP SDK。

stdio 生命周期：

建立 stdio transport
→ 建立 ClientSession
→ initialize
→ list_tools / call_tool
→ close session
→ close transport

必须：

try/finally
或
async context manager

确保异常时也释放子进程和 pipe。

==================================================
九、Tool Discovery
==================================================

list_tools()：

真实调用 MCP Server 的 tools/list。

返回：

list[McpRemoteTool]

映射至少包括：

- name
- description
- inputSchema

要求：

name：
非空。

inputSchema：
必须为 JSON object schema。

如果：

inputSchema 不是 dict/object

返回：

MCP_TOOL_SCHEMA_INVALID

不要自动修复 schema。

==================================================
十、MCP Tool -> 当前 ToolDefinition
==================================================

4-6A 提供一个纯转换函数：

McpRemoteTool
→ ToolDefinition

复用 4-5 已有：

ToolDefinition

映射：

remote.name
→ ToolDefinition.name

remote.description
→ description

remote.input_schema
→ parameters_schema

但本阶段还不要做 Agent Tool 命名冲突处理。

内部 MCP namespacing 留到 4-6B。

这里只验证 schema 能转换。

==================================================
十一、call_tool
==================================================

实现：

McpClient.call_tool()

输入：

config
tool_name
arguments: dict

必须调用 MCP：

tools/call

不要自己模拟执行。

返回统一：

McpToolResult

至少支持 MCP text content。

如果 SDK 支持 structuredContent：
同时解析为 structured_data。

不要把 SDK内部对象 repr 返回上层。

==================================================
十二、Result 规范化
==================================================

如果 MCP 返回：

text content

将文本安全拼接到：

content

如果 structured content：

放到：

structured_data

如果：

无 text
也无 structured result

返回：

MCP_TOOL_EMPTY_RESULT

不要自动制造空结果。

==================================================
十三、错误定义
==================================================

定义 MCP 独立错误。

至少：

McpError

以及安全错误码：

MCP_CONFIG_INVALID
MCP_TRANSPORT_UNSUPPORTED
MCP_CREDENTIAL_MISSING
MCP_SERVER_CONNECT_FAILED
MCP_LIST_TOOLS_FAILED
MCP_TOOL_SCHEMA_INVALID
MCP_TOOL_NOT_FOUND
MCP_TOOL_ARGUMENTS_INVALID
MCP_TOOL_EXECUTION_FAILED
MCP_TOOL_EMPTY_RESULT

异常对外不得包含：

- secret
- command完整敏感参数
- traceback
- SDK内部错误详情

==================================================
十四、测试 MCP Server
==================================================

建立最小真实 MCP stdio 测试 Server。

建议：

backend/tests/mcp/fixtures/test_server.py

使用官方 MCP SDK 创建。

只提供：

add_numbers

参数：

{
  "a": number,
  "b": number
}

结果：

{
  "result": a + b
}

不要实现健康业务 Tool。

不要使用 mock 替代整个 MCP 协议。

==================================================
十五、stdio 真实集成测试
==================================================

必须真正启动测试 MCP Server。

验证：

McpClient
→ stdio subprocess
→ MCP initialize
→ list_tools
→ call_tool

测试：

2 + 3

结果：

5

必须确认：

- Server 真正启动
- MCP handshake 成功
- list_tools 成功
- add_numbers 被发现
- inputSchema 正常
- call_tool 真正执行
- result 正确
- 子进程正常退出

==================================================
十六、测试覆盖
==================================================

新增：

backend/tests/mcp/__init__.py
backend/tests/mcp/test_config.py
backend/tests/mcp/test_client.py
backend/tests/mcp/test_stdio.py
backend/tests/mcp/test_security.py

必须覆盖：

Config：

- valid stdio
- transport missing
- unsupported transport
- command missing
- args 非 list[str]
- env 格式非法
- env secret exists
- env secret missing

Security：

- cmd.exe 拒绝
- powershell.exe 拒绝
- pwsh 拒绝
- bash/sh 拒绝
- command 不允许通过 arguments 覆盖
- 不使用 shell=True

Discovery：

- MCP initialize 成功
- list_tools 成功
- add_numbers 存在
- description 正常
- inputSchema 是 object
- 非法 schema 拒绝

Invocation：

- 2+3=5
- 参数传递正确
- 不存在 Tool -> MCP_TOOL_NOT_FOUND
- Server执行失败 -> MCP_TOOL_EXECUTION_FAILED
- empty result -> MCP_TOOL_EMPTY_RESULT

Lifecycle：

- 正常调用后 child process 退出
- 异常调用后 child process 也退出
- 不残留 MCP process

==================================================
十七、不要接 Runtime
==================================================

本阶段禁止修改：

AgentRuntimeService Tool Loop

不要让 Agent：

DeepSeek
→ MCP

这是 4-6B。

4-6A 的验收边界必须停在：

Python Test
→ McpClient
→ stdio MCP Server
→ add_numbers
→ result

==================================================
十八、不要修改数据库
==================================================

本阶段原则：

不创建 MCP Tool DB record。

不修改：

Tool Model
Agent config
Repository
Schema
Migration

只验证 MCP Client 基础。

Alembic head 必须保持：

20260818_0002

==================================================
十九、测试执行
==================================================

使用官方：

python:3.12-slim

安装新增 MCP SDK 后运行：

python -m pytest backend/tests/mcp -v

要求：

failed = 0
errors = 0
skipped = 0

然后执行：

python -m pytest backend/tests -v

要求：

failed = 0
errors = 0
skipped = 0

如果 MCP 测试需要 subprocess：

确保 Docker 容器内可以正常启动测试 server。

不要依赖宿主机 Python。

==================================================
二十、资源残留
==================================================

测试完成必须确认：

MCP child process residual = 0

不要留下：

- 测试 Server
- pipe
- temp file
- subprocess

如果创建临时文件：

finally 删除。

==================================================
二十一、最终确认
==================================================

4-6A 完成条件：

- 官方 MCP SDK 已接入
- MCP SDK版本明确
- McpServerConfig 可用
- env secret resolver 可用
- stdio 安全校验可用
- McpClient.list_tools 可用
- McpClient.call_tool 可用
- MCP initialize 成功
- add_numbers 可真实发现
- 2+3=5 可真实执行
- MCP Result 已规范化
- MCP Error 已安全映射
- ToolDefinition 转换基础可用
- child process residual=0
- MCP专项 0 failed/errors/skipped
- 全量 0 failed/errors/skipped
- Alembic head=20260818_0002
- 未修改 Schema/Migration
- 未接 Agent Runtime
- 未实现 HTTP MCP
- 未实现 RAG+MCP
- 未实现 Multi-Agent

==================================================
二十二、报告
==================================================

生成：

readme/4-6A-MCP-Client-stdio基础.md

记录：

1. Langflow / Dify参考点
2. MCP SDK名称与版本
3. MCP Client结构
4. McpServerConfig
5. stdio transport
6. ClientSession 生命周期
7. env secret resolver
8. stdio command安全规则
9. list_tools
10. call_tool
11. McpRemoteTool
12. McpToolResult
13. ToolDefinition基础转换
14. 错误映射
15. test MCP Server
16. add_numbers测试
17. child process清理
18. MCP专项结果
19. 全量测试结果
20. Alembic head
21. 是否修改Schema/Migration
22. 是否接入Runtime

如果全部完成，写：

“4-6A MCP Client + stdio 基础验收完成，可封板。”

完成后停止。

不要继续 4-6B。

只有：
1. 全部完成；
或
2. 官方 MCP SDK 当前版本的 stdio API存在真实结构性阻塞

时再回复。