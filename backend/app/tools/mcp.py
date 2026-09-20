"""Adapter that exposes one discovered MCP tool as a normal runtime handler."""
from __future__ import annotations

from typing import Any, Mapping

from backend.app.mcp import McpClient, McpError, parse_server_config
from backend.app.exceptions import ValidationError
from backend.app.tools.base import ToolHandler, ToolResult


class McpToolAdapter(ToolHandler):
    def __init__(self, *, client: McpClient, server: Mapping[str, Any], remote_name: str) -> None:
        self.client = client
        self.server = dict(server)
        self.remote_name = remote_name
        self.name = remote_name
        self.description = remote_name
        self.parameters_schema: dict[str, Any] = {"type": "object"}

    async def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            result = await self.client.call_tool(parse_server_config(self.server), self.remote_name, dict(arguments))
        except McpError as exc:
            raise ValidationError(exc.code) from exc
        return ToolResult(result.success, result.content, result.structured_data if isinstance(result.structured_data, dict) else None)
