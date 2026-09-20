"""Small, bounded coordinator/sub-agent orchestration layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID
from backend.app.exceptions import ValidationError, NotFoundError
from backend.app.model_gateway.chat import ChatInput, chat_provider_for
from backend.app.tools import ToolDefinition, ToolResult


@dataclass
class MultiAgentExecutionContext:
    root_agent_id: UUID
    current_agent_id: UUID
    depth: int = 0
    handoff_count: int = 0
    visited_agents: set[UUID] = field(default_factory=set)
    parent_run_id: UUID | None = None
    user_id: UUID | None = None
    conversation_id: UUID | None = None


class SubAgentHandler:
    def __init__(self, orchestrator, agent, context):
        self.orchestrator, self.agent, self.context = orchestrator, agent, context

    async def execute(self, arguments):
        task = arguments.get("task") if isinstance(arguments, dict) else None
        if not isinstance(task, str) or not task.strip():
            raise ValidationError("SUB_AGENT_TASK_INVALID")
        result = await self.orchestrator.execute_sub_agent(self.agent, task, self.context)
        return ToolResult(True, result)


class MultiAgentOrchestrator:
    MAX_DEPTH = 3
    MAX_RESULT_CHARS = 12000

    def __init__(self, runtime):
        self.runtime = runtime
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def definitions(self, coordinator, context):
        cfg = coordinator.config.get("multi_agent", {}) if isinstance(coordinator.config, dict) else {}
        if cfg.get("enabled") is not True:
            return [], 0
        ids = cfg.get("sub_agent_ids", [])
        if not isinstance(ids, list):
            raise ValidationError("MULTI_AGENT_CONFIG_INVALID")
        max_handoffs = cfg.get("max_handoffs", 3)
        if isinstance(max_handoffs, bool) or not isinstance(max_handoffs, int) or not 1 <= max_handoffs <= 10:
            raise ValidationError("MULTI_AGENT_CONFIG_INVALID")
        definitions = []
        for raw in ids:
            try: aid = UUID(str(raw))
            except (TypeError, ValueError) as exc: raise ValidationError("MULTI_AGENT_CONFIG_INVALID") from exc
            if aid == coordinator.id: raise ValidationError("MULTI_AGENT_SELF_REFERENCE")
            agent = await self.runtime.agents.get_by_id(aid)
            if agent is None: raise NotFoundError("SUB_AGENT_NOT_FOUND")
            if agent.status != "active": raise ValidationError("SUB_AGENT_INACTIVE")
            name = "agent__" + "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in agent.code)
            definitions.append(ToolDefinition(name, agent.description or agent.name, {"type":"object","properties":{"task":{"type":"string"}},"required":["task"],"additionalProperties":False}, handler=SubAgentHandler(self, agent, context)))
        return definitions, max_handoffs

    async def execute_sub_agent(self, agent, task, parent_context):
        if parent_context.depth >= self.MAX_DEPTH: raise ValidationError("MULTI_AGENT_MAX_HANDOFFS_EXCEEDED")
        if agent.id in parent_context.visited_agents: raise ValidationError("MULTI_AGENT_CYCLE_DETECTED")
        if parent_context.handoff_count >= 10: raise ValidationError("MULTI_AGENT_MAX_HANDOFFS_EXCEEDED")
        if agent.model_config_id is None: raise ValidationError("SUB_AGENT_MODEL_INVALID")
        config = await self.runtime.configs.get_by_id(agent.model_config_id)
        if config is None or config.status != "active" or config.model_type != "chat": raise ValidationError("SUB_AGENT_MODEL_INVALID")
        provider = await self.runtime.providers.get_by_id(config.provider_id)
        if provider is None or provider.status != "active": raise ValidationError("SUB_AGENT_MODEL_INVALID")
        child = None
        if parent_context.user_id is not None and parent_context.conversation_id is not None:
            if parent_context.parent_run_id is None:
                raise ValidationError("MULTI_AGENT_INTERNAL_RUN_BLOCKER")
            child = await self.runtime.runs.create_child_agent_run(
                user_id=parent_context.user_id,
                child_agent_id=agent.id,
                conversation_id=parent_context.conversation_id,
                parent_run_id=parent_context.parent_run_id,
                root_agent_id=parent_context.root_agent_id,
                model_config_id=config.id,
                input_summary=task,
                risk_level="low",
                safety_status="safe",
            )
            await self.runtime.runs.update_agent_run(child.id, status="running")
        ctx = MultiAgentExecutionContext(parent_context.root_agent_id, agent.id, parent_context.depth + 1, parent_context.handoff_count + 1, set(parent_context.visited_agents) | {agent.id}, child.id if child else parent_context.parent_run_id)
        ctx.user_id, ctx.conversation_id = parent_context.user_id, parent_context.conversation_id
        started = __import__("time").perf_counter()
        try:
            history = await self.runtime._messages_with_rag(agent, task, [ChatInput("user", task)])
            defs, maximum = await self.runtime._tool_definitions(agent)
            nested_defs, nested_max = await self.definitions(agent, ctx)
            defs = [*defs, *nested_defs]
            maximum = max(maximum, nested_max)
            result, prompt, completion = await self.runtime._chat_with_tools(chat_provider_for(provider.provider_type, secret_ref=provider.secret_ref, endpoint=provider.endpoint), list(history), config, defs, maximum)
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            text = result.content[: self.MAX_RESULT_CHARS]
            if child:
                await self.runtime.runs.update_agent_run(child.id, status="succeeded", output_summary=text, prompt_tokens=prompt, completion_tokens=completion, latency_ms=int((__import__("time").perf_counter()-started)*1000))
            return text
        except Exception as exc:
            if child:
                await self.runtime.runs.update_agent_run(child.id, status="failed", error_code="multi_agent_child_error", error_message="Sub-agent execution failed", latency_ms=int((__import__("time").perf_counter()-started)*1000))
            raise
