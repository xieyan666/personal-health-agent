import pytest

from backend.app.mcp import McpClient, McpServerConfig


@pytest.mark.asyncio
async def test_stdio_real_server_lifecycle():
    config = McpServerConfig("stdio", "python", ["backend/tests/mcp/fixtures/test_server.py"])
    client = McpClient()
    assert any(tool.name == "add_numbers" for tool in await client.list_tools(config))
    result = await client.call_tool(config, "add_numbers", {"a": 2, "b": 3})
    assert result.content and "5" in result.content
