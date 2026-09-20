"""Basic persisted agent runtime execution chain."""

from dataclasses import dataclass
from time import perf_counter
from uuid import UUID
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.model_gateway.chat import ChatInput, MIN_TOOL_MAX_TOKENS, chat_provider_for, normalize_chat_parameters
from backend.app.repositories import AgentRepository, ConversationRepository, ModelConfigRepository, ModelProviderRepository, UserRepository
from backend.app.services.conversation import MessageService
from backend.app.services.execution import AgentRunService
from backend.app.services.exceptions import NotFoundError, ValidationError
from backend.app.services.rag import RagService
from backend.app.services.tool import ToolService
from backend.app.tools import ToolCall, ToolDefinition, ToolExecutor
from backend.app.mcp import McpClient, McpError, parse_server_config, to_tool_definition
from backend.app.tools.mcp import McpToolAdapter
from backend.app.agent.multi_agent import MultiAgentExecutionContext, MultiAgentOrchestrator


@dataclass(frozen=True)
class RuntimeResult:
    run_id: UUID
    run_status: str
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    assistant_content: str


class AgentRuntimeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.agents = AgentRepository(session)
        self.conversations = ConversationRepository(session)
        self.configs = ModelConfigRepository(session)
        self.providers = ModelProviderRepository(session)
        self.messages = MessageService(session)
        self.runs = AgentRunService(session)
        self.rag = RagService(session)
        self.tools = ToolService(session)
        self.tool_executor = ToolExecutor()
        self._mcp_discovery: dict[str, tuple[dict, object]] = {}
        self.multi_agent = MultiAgentOrchestrator(self)

    async def _tool_definitions(self, agent):
        cfg = agent.config.get("tools", {}) if isinstance(agent.config, dict) else {}
        if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
            return [], 0
        raw_ids = cfg.get("tool_ids")
        if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 20:
            raise ValidationError("Agent tools requires 1 to 20 tool_ids")
        try: ids = list(dict.fromkeys(UUID(str(value)) for value in raw_ids))
        except (TypeError, ValueError) as exc: raise ValidationError("Agent tool_ids must be UUIDs") from exc
        maximum = cfg.get("max_iterations", 5)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 10:
            raise ValidationError("Agent tools max_iterations must be between 1 and 10")
        definitions = []
        for tool_id in ids:
            tool = await self.tools.get_tool(tool_id)
            if tool.status != "active": raise ValidationError("Agent tool is not active")
            if tool.tool_type != "mcp":
                definitions.append(ToolDefinition(tool.name, tool.display_name, tool.input_schema))
                continue
            config = tool.config if isinstance(tool.config, dict) else {}
            server = config.get("server") if isinstance(config.get("server"), dict) else config
            remote_name = config.get("remote_tool_name")
            if not isinstance(server, dict) or not isinstance(remote_name, str) or not remote_name:
                raise ValidationError("MCP_CONFIG_INVALID")
            parsed = parse_server_config(server)
            cache_key = repr((parsed.transport, parsed.command, parsed.args, parsed.url, sorted(parsed.env.items()), sorted(parsed.headers.items())))
            cached = self._mcp_discovery.get(cache_key)
            if cached is None:
                try:
                    discovered = await McpClient().list_tools(parsed)
                except McpError as exc:
                    raise ValidationError(exc.code) from exc
                remote_tools = {item.name: item for item in discovered}
                self._mcp_discovery[cache_key] = (server, remote_tools)
            else:
                remote_tools = cached[1]
            if remote_name not in remote_tools:
                raise ValidationError("MCP_TOOL_NOT_FOUND")
            remote = remote_tools[remote_name]
            alias = config.get("server_alias") or tool.name
            internal_name = "mcp__" + "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(alias)) + "__" + remote_name
            adapter = McpToolAdapter(client=McpClient(), server=server, remote_name=remote_name)
            definitions.append(ToolDefinition(internal_name, remote.description or tool.display_name, remote.input_schema, handler=adapter))
        return definitions, maximum

    async def _chat_with_tools(self, provider, history, config, definitions, maximum, *, max_tokens_override=None):
        parameters = normalize_chat_parameters(config.parameters, max_tokens_override=max_tokens_override)
        if definitions and parameters["max_tokens"] < MIN_TOOL_MAX_TOKENS:
            raise ValidationError("TOOL_TOKEN_BUDGET_TOO_SMALL")
        prompt = completion = 0
        for _ in range(maximum or 1):
            result = provider.chat(history, model_name=config.model_name, parameters=parameters, tools=[item.as_openai_tool() for item in definitions] or None)
            prompt += result.prompt_tokens; completion += result.completion_tokens
            if result.finish_reason == "length" and result.tool_calls:
                raise ValidationError("TOOL_CALL_TRUNCATED")
            if not result.tool_calls:
                return result, prompt, completion
            if not definitions: raise ValidationError("Tool calls are disabled")
            by_name = {item.name: item for item in definitions}
            history.append(ChatInput("assistant", result.content, tool_calls=result.tool_calls))
            for call in result.tool_calls:
                definition = by_name.get(call.name)
                if definition is None: raise ValidationError("Tool call is not authorized")
                output = await self.tool_executor.execute(definition, call)
                history.append(ChatInput("tool", output.content, tool_call_id=call.id))
        raise ValidationError("tool iteration limit exceeded")

    async def _messages_with_rag(self, agent, content: str, history):
        config = agent.config
        if not isinstance(config, dict):
            raise ValidationError("Agent config must be an object")
        base_history = list(history)
        rag = config.get("rag", {})
        if rag is None or rag == {}:
            return history
        if not isinstance(rag, dict):
            raise ValidationError("Agent rag config must be an object")
        if rag.get("enabled") is not True:
            return history
        try:
            knowledge_base_id = UUID(str(rag["knowledge_base_id"]))
            embedding_model_config_id = UUID(str(rag["embedding_model_config_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Agent rag config requires valid knowledge_base_id and embedding_model_config_id") from exc
        top_k = rag.get("top_k", 5)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            raise ValidationError("Agent rag top_k must be an integer between 1 and 20")
        context = await self.rag.build_context(knowledge_base_id, content, embedding_model_config_id, top_k)
        if not context.context_text:
            return history
        system = "你可以参考以下企业知识库内容回答用户问题。\n仅在知识库内容与用户问题相关时使用。\n如果知识库没有提供答案，不要编造。\n\n[KNOWLEDGE_CONTEXT]\n" + context.context_text + "\n[/KNOWLEDGE_CONTEXT]"
        # Provider APIs expect the policy/context message before the user
        # history so it is applied as the conversation's system instruction.
        return [ChatInput("system", system), *base_history]

    async def run(self, user_id: UUID, agent_id: UUID, conversation_id: UUID, content: str) -> RuntimeResult:
        self._mcp_discovery = {}
        self.multi_agent.prompt_tokens = 0
        self.multi_agent.completion_tokens = 0
        if not content or not content.strip():
            raise ValidationError("content must not be empty")
        if await self.users.get_by_id(user_id) is None:
            raise NotFoundError(f"User not found: {user_id}")
        agent = await self.agents.get_by_id(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent not found: {agent_id}")
        if agent.status != "active":
            raise ValidationError("Agent is not active")
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        if conversation.user_id != user_id:
            raise ValidationError("Conversation belongs to another user")
        if conversation.agent_id != agent_id:
            raise ValidationError("Conversation belongs to another agent")
        if agent.model_config_id is None:
            raise ValidationError("Agent requires model_config_id")
        config = await self.configs.get_by_id(agent.model_config_id)
        if config is None:
            raise NotFoundError(f"Model config not found: {agent.model_config_id}")
        if config.status != "active" or config.model_type != "chat":
            raise ValidationError("Agent model config is not an active chat model")
        provider = await self.providers.get_by_id(config.provider_id)
        if provider is None:
            raise NotFoundError(f"Model provider not found: {config.provider_id}")
        if provider.status != "active":
            raise ValidationError("Model provider is not active")
        user_message = await self.messages.create_message(conversation_id=conversation_id, role="user", content=content, content_data={}, status="succeeded", source_reference={}, risk_level="low", safety_status="safe")
        run = await self.runs.create_agent_run(user_id=user_id, agent_id=agent_id, conversation_id=conversation_id, trigger_message_id=user_message.id, model_config_id=config.id, status="pending", input_summary=content, risk_level="low", safety_status="safe")
        await self.runs.update_agent_run(run.id, status="running")
        started = perf_counter()
        try:
            history = await self.messages.list_messages(conversation_id, limit=100)
            history = await self._messages_with_rag(agent, content, [ChatInput(message.role, message.content) for message in history])
            definitions, maximum = await self._tool_definitions(agent)
            multi_defs, multi_max = await self.multi_agent.definitions(agent, MultiAgentExecutionContext(agent.id, agent.id, visited_agents={agent.id}, parent_run_id=run.id, user_id=user_id, conversation_id=conversation_id))
            definitions = [*definitions, *multi_defs]
            maximum = max(maximum, multi_max)
            result, total_prompt, total_completion = await self._chat_with_tools(chat_provider_for(provider.provider_type, secret_ref=provider.secret_ref, endpoint=provider.endpoint), list(history), config, definitions, maximum)
            total_prompt += self.multi_agent.prompt_tokens
            total_completion += self.multi_agent.completion_tokens
            assistant = await self.messages.create_message(conversation_id=conversation_id, parent_message_id=user_message.id, role="assistant", content=result.content, content_data={}, status="succeeded", source_reference={}, risk_level="low", safety_status="safe")
            completed = await self.runs.update_agent_run(run.id, status="succeeded", output_message_id=assistant.id, output_summary=result.content, prompt_tokens=total_prompt, completion_tokens=total_completion, latency_ms=int((perf_counter() - started) * 1000))
            return RuntimeResult(completed.id, completed.status, conversation_id, user_message.id, assistant.id, result.content)
        except Exception as exc:
            await self.runs.update_agent_run(run.id, status="failed", error_code="runtime_error", error_message=str(exc), latency_ms=int((perf_counter() - started) * 1000))
            raise

    async def stream_run(self, user_id: UUID, agent_id: UUID, conversation_id: UUID, content: str) -> AsyncIterator[dict]:
        self._mcp_discovery = {}
        self.multi_agent.prompt_tokens = 0
        self.multi_agent.completion_tokens = 0
        if not content or not content.strip():
            raise ValidationError("content must not be empty")
        if await self.users.get_by_id(user_id) is None:
            raise NotFoundError(f"User not found: {user_id}")
        agent = await self.agents.get_by_id(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent not found: {agent_id}")
        if agent.status != "active":
            raise ValidationError("Agent is not active")
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        if conversation.user_id != user_id or conversation.agent_id != agent_id:
            raise ValidationError("Conversation does not match user and agent")
        if agent.model_config_id is None:
            raise ValidationError("Agent requires model_config_id")
        config = await self.configs.get_by_id(agent.model_config_id)
        if config is None:
            raise NotFoundError(f"Model config not found: {agent.model_config_id}")
        if config.status != "active" or config.model_type != "chat":
            raise ValidationError("Agent model config is not an active chat model")
        provider = await self.providers.get_by_id(config.provider_id)
        if provider is None:
            raise NotFoundError(f"Model provider not found: {config.provider_id}")
        if provider.status != "active":
            raise ValidationError("Model provider is not active")
        user_message = await self.messages.create_message(conversation_id=conversation_id, role="user", content=content, content_data={}, status="succeeded", source_reference={}, risk_level="low", safety_status="safe")
        run = await self.runs.create_agent_run(user_id=user_id, agent_id=agent_id, conversation_id=conversation_id, trigger_message_id=user_message.id, model_config_id=config.id, status="pending", input_summary=content, risk_level="low", safety_status="safe")
        await self.runs.update_agent_run(run.id, status="running")
        yield {"type": "run_started", "run_id": str(run.id), "conversation_id": str(conversation_id), "user_message_id": str(user_message.id)}
        started = perf_counter()
        assembled: list[str] = []
        prompt_tokens = completion_tokens = total_tokens = 0
        try:
            history = await self.messages.list_messages(conversation_id, limit=100)
            history = await self._messages_with_rag(agent, content, [ChatInput(message.role, message.content) for message in history])
            definitions, maximum = await self._tool_definitions(agent)
            multi_defs, multi_max = await self.multi_agent.definitions(agent, MultiAgentExecutionContext(agent.id, agent.id, visited_agents={agent.id}, parent_run_id=run.id, user_id=user_id, conversation_id=conversation_id))
            definitions = [*definitions, *multi_defs]
            maximum = max(maximum, multi_max)
            provider_impl = chat_provider_for(provider.provider_type, secret_ref=provider.secret_ref, endpoint=provider.endpoint)
            parameters = normalize_chat_parameters(config.parameters)
            if definitions and parameters["max_tokens"] < MIN_TOOL_MAX_TOKENS:
                raise ValidationError("TOOL_TOKEN_BUDGET_TOO_SMALL")
            runtime_history = list(history)
            definition_by_name = {item.name: item for item in definitions}
            for _ in range(maximum or 1):
                calls = ()
                async for event in provider_impl.stream_chat(runtime_history, model_name=config.model_name, parameters=parameters, tools=[item.as_openai_tool() for item in definitions] or None):
                    if event.type == "delta" and event.content_delta:
                        assembled.append(event.content_delta)
                        yield {"type": "message_delta", "delta": event.content_delta}
                    elif event.type == "usage":
                        prompt_tokens += event.prompt_tokens; completion_tokens += event.completion_tokens; total_tokens += event.total_tokens
                    elif event.type == "tool_calls":
                        calls = event.tool_calls
                if not calls:
                    break
                if not definitions:
                    raise ValidationError("Tool calls are disabled")
                for call in calls:
                    definition = definition_by_name.get(call.name)
                    if definition is None:
                        raise ValidationError("Tool call is not authorized")
                    is_agent_call = call.name.startswith("agent__")
                    if is_agent_call:
                        yield {"type": "agent_call_started", "agent_call_id": call.id, "agent_name": call.name}
                    else:
                        yield {"type": "tool_call_started", "tool_call_id": call.id, "tool_name": call.name}
                    output = await self.tool_executor.execute(definition, call)
                    runtime_history.append(ChatInput("assistant", "", tool_calls=(call,)))
                    runtime_history.append(ChatInput("tool", output.content, tool_call_id=call.id))
                    if is_agent_call:
                        yield {"type": "agent_call_completed", "agent_call_id": call.id, "agent_name": call.name, "success": output.success}
                    else:
                        yield {"type": "tool_call_completed", "tool_call_id": call.id, "tool_name": call.name, "success": output.success}
            else:
                raise ValidationError("tool iteration limit exceeded")
            final_content = "".join(assembled)
            prompt_tokens += self.multi_agent.prompt_tokens
            completion_tokens += self.multi_agent.completion_tokens
            assistant = await self.messages.create_message(conversation_id=conversation_id, parent_message_id=user_message.id, role="assistant", content=final_content, content_data={}, status="succeeded", source_reference={}, risk_level="low", safety_status="safe")
            completed = await self.runs.update_agent_run(run.id, status="succeeded", output_message_id=assistant.id, output_summary=final_content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, latency_ms=int((perf_counter() - started) * 1000))
            yield {"type": "run_completed", "run_id": str(completed.id), "assistant_message_id": str(assistant.id), "status": "succeeded", "prompt_tokens": completed.prompt_tokens, "completion_tokens": completed.completion_tokens, "latency_ms": completed.latency_ms}
        except BaseException as exc:
            status = "cancelled" if isinstance(exc, __import__("asyncio").CancelledError) else "failed"
            await self.runs.update_agent_run(run.id, status=status, error_code="stream_cancelled" if status == "cancelled" else "stream_error", error_message="Stream execution failed" if status == "failed" else "Stream cancelled", latency_ms=int((perf_counter() - started) * 1000))
            if status == "cancelled":
                raise
            yield {"type": "error", "run_id": str(run.id), "status": "failed", "error_code": "stream_error", "message": "Stream execution failed"}
