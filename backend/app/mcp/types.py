from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.tools.base import ToolDefinition


@dataclass(frozen=True)
class McpServerConfig:
    transport: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    allow_private_network: bool = False


@dataclass(frozen=True)
class McpRemoteTool:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class McpToolResult:
    success: bool
    content: str
    structured_data: Any | None = None


def to_tool_definition(tool: McpRemoteTool) -> ToolDefinition:
    return ToolDefinition(tool.name, tool.description, tool.input_schema)
