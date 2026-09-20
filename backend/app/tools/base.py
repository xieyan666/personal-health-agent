"""Safe, explicitly registered runtime tool contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

from backend.app.exceptions import ValidationError


class ToolExecutionError(Exception):
    """A safe, user-independent tool execution failure."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler | None = None

    def as_openai_tool(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    success: bool
    content: str
    structured_data: dict[str, Any] | None = None


class ToolHandler:
    name: str
    description: str
    parameters_schema: dict[str, Any]

    async def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        raise NotImplementedError


def require_object_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValidationError("Tool input_schema must be a JSON Schema object")
    return schema
