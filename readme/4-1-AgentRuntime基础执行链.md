# 4-1 Agent Runtime 基础执行链

## 参考设计

参考 Langflow 的执行上下文与模型调用入口、Dify 的 Conversation/Message/Run 分离组织：对话消息独立持久化，Run 记录状态与输出引用，模型调用入口可替换。

## 实现

- FakeChatProvider：网络隔离、确定性输出。
- AgentRuntimeService：校验 User/Agent/Conversation/ModelConfig/Provider 关系，写 User Message，创建并推进 AgentRun，调用 FakeChatProvider，再写 Assistant Message。
- 成功状态：pending → running → succeeded；失败进入 failed，不创建 Assistant Message。
- API：`POST /api/v1/agents/{agent_id}/run`。

未修改 Schema/Migration，未实现真实模型、SSE、RAG、Tool/MCP 或 Agent Runtime 的后续能力。

## 验证

- 异常类唯一来源：`backend.app.exceptions`；`backend.app.services.exceptions` 仅兼容 re-export，异常类型身份一致。
- Python 3.12.14 静态导入：embedding、chat、services、main 均正常，无循环导入。
- 专项：3 passed、0 failed、0 errors、0 skipped。
- 全量：75 passed、0 failed、0 errors、0 skipped。
- FakeChatProvider 为纯本地确定性实现，无网络或真实模型调用。
