from __future__ import annotations
from backend.app.exceptions import ValidationError
from backend.app.tools.base import ToolCall, ToolResult, require_object_schema
from backend.app.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    async def execute(self, definition, call: ToolCall) -> ToolResult:
        if call.name != definition.name:
            raise ValidationError("Tool call is not authorized for this agent")
        require_object_schema(definition.parameters)
        handler = getattr(definition, "handler", None) or self.registry.get(call.name)
        return await handler.execute(call.arguments)
