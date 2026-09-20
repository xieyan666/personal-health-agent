from __future__ import annotations

from typing import Any, Mapping
import asyncio
import ssl

from backend.app.mcp.config import parse_server_config
from backend.app.mcp.errors import *
from backend.app.mcp.types import McpRemoteTool, McpServerConfig, McpToolResult


def _schema(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") != "object":
        raise McpError(MCP_TOOL_SCHEMA_INVALID)
    return value


class McpClient:
    async def list_tools(self, config: McpServerConfig | Mapping[str, Any]) -> list[McpRemoteTool]:
        config = parse_server_config(config) if isinstance(config, Mapping) else config
        if config.transport == "streamable_http":
            return await self._http_list_tools(config)
        if config.transport != "stdio":
            raise McpError(MCP_TRANSPORT_UNSUPPORTED)
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            async with stdio_client(StdioServerParameters(command=config.command, args=config.args, env=config.env or None)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = []
                    for item in result.tools:
                        name = getattr(item, "name", "")
                        if not isinstance(name, str) or not name.strip():
                            raise McpError(MCP_TOOL_SCHEMA_INVALID)
                        tools.append(McpRemoteTool(name, str(getattr(item, "description", "") or ""), _schema(getattr(item, "inputSchema", None))))
                    return tools
        except McpError:
            raise
        except Exception as exc:
            raise McpError(MCP_LIST_TOOLS_FAILED) from exc

    async def call_tool(self, config: McpServerConfig | Mapping[str, Any], tool_name: str, arguments: dict[str, Any]) -> McpToolResult:
        config = parse_server_config(config) if isinstance(config, Mapping) else config
        if config.transport == "streamable_http":
            return await self._http_call_tool(config, tool_name, arguments)
        if not isinstance(tool_name, str) or not tool_name.strip() or not isinstance(arguments, dict):
            raise McpError(MCP_TOOL_ARGUMENTS_INVALID)
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            async with stdio_client(StdioServerParameters(command=config.command, args=config.args, env=config.env or None)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if getattr(result, "isError", False):
                        raise McpError(MCP_TOOL_EXECUTION_FAILED)
                    content_parts = [item.text for item in getattr(result, "content", []) if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str)]
                    structured = getattr(result, "structuredContent", None)
                    if not content_parts and structured is None:
                        raise McpError(MCP_TOOL_EMPTY_RESULT)
                    return McpToolResult(True, "\n".join(content_parts), structured)
        except McpError:
            raise
        except Exception as exc:
            raise McpError(MCP_TOOL_EXECUTION_FAILED) from exc

    async def _http_list_tools(self, config: McpServerConfig) -> list[McpRemoteTool]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
            async with streamablehttp_client(config.url, headers=config.headers or None, timeout=30, sse_read_timeout=30) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = []
                    for item in result.tools:
                        name = getattr(item, "name", "")
                        if not isinstance(name, str) or not name.strip():
                            raise McpError(MCP_TOOL_SCHEMA_INVALID)
                        tools.append(McpRemoteTool(name, str(getattr(item, "description", "") or ""), _schema(getattr(item, "inputSchema", None))))
                    return tools
        except asyncio.TimeoutError as exc:
            raise McpError(MCP_HTTP_TIMEOUT) from exc
        except ssl.SSLError as exc:
            raise McpError(MCP_HTTP_TLS_FAILED) from exc
        except McpError:
            raise
        except Exception as exc:
            raise McpError(MCP_HTTP_CONNECT_FAILED) from exc

    async def _http_call_tool(self, config: McpServerConfig, tool_name: str, arguments: dict[str, Any]) -> McpToolResult:
        if not isinstance(tool_name, str) or not tool_name.strip() or not isinstance(arguments, dict):
            raise McpError(MCP_TOOL_ARGUMENTS_INVALID)
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
            async with streamablehttp_client(config.url, headers=config.headers or None, timeout=30, sse_read_timeout=30) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if getattr(result, "isError", False):
                        raise McpError(MCP_TOOL_EXECUTION_FAILED)
                    content_parts = [item.text for item in getattr(result, "content", []) if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str)]
                    structured = getattr(result, "structuredContent", None)
                    if not content_parts and structured is None:
                        raise McpError(MCP_TOOL_EMPTY_RESULT)
                    return McpToolResult(True, "\n".join(content_parts), structured)
        except asyncio.TimeoutError as exc:
            raise McpError(MCP_HTTP_TIMEOUT) from exc
        except ssl.SSLError as exc:
            raise McpError(MCP_HTTP_TLS_FAILED) from exc
        except McpError:
            raise
        except Exception as exc:
            raise McpError(MCP_HTTP_CONNECT_FAILED) from exc
