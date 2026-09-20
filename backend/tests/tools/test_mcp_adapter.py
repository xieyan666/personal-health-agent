import pytest

from backend.app.mcp import McpClient
from backend.app.tools.base import ToolCall, ToolDefinition
from backend.app.tools.executor import ToolExecutor
from backend.app.tools.mcp import McpToolAdapter


@pytest.mark.asyncio
async def test_mcp_adapter_executes_stdio_tool():
    server = {"transport": "stdio", "command": "python", "args": ["backend/tests/mcp/fixtures/test_server.py"]}
    adapter = McpToolAdapter(client=McpClient(), server=server, remote_name="add_numbers")
    definition = ToolDefinition("mcp__test_server__add_numbers", "Add", {"type": "object"}, handler=adapter)
    result = await ToolExecutor().execute(definition, ToolCall(definition.name, definition.name, {"a": 2, "b": 3}))
    assert result.success is True
    assert "5" in result.content


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_bad_arguments():
    server = {"transport": "stdio", "command": "python", "args": ["backend/tests/mcp/fixtures/test_server.py"]}
    adapter = McpToolAdapter(client=McpClient(), server=server, remote_name="add_numbers")
    definition = ToolDefinition("mcp__test_server__add_numbers", "Add", {"type": "object"}, handler=adapter)
    with pytest.raises(Exception):
        await ToolExecutor().execute(definition, ToolCall(definition.name, definition.name, {"a": 2}))
