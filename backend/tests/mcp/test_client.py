import pytest

from backend.app.mcp import McpClient, McpError, McpServerConfig, to_tool_definition


SERVER = "backend/tests/mcp/fixtures/test_server.py"


@pytest.fixture
def config():
    return McpServerConfig("stdio", "python", [SERVER])


@pytest.mark.asyncio
async def test_list_tools_discovers_add_numbers(config):
    tools = await McpClient().list_tools(config)
    add = next(item for item in tools if item.name == "add_numbers")
    assert add.description == "Add two numbers."
    assert add.input_schema["type"] == "object"
    assert to_tool_definition(add).name == "add_numbers"


@pytest.mark.asyncio
async def test_call_tool_returns_five(config):
    result = await McpClient().call_tool(config, "add_numbers", {"a": 2, "b": 3})
    assert result.success is True
    assert "5" in result.content


@pytest.mark.asyncio
async def test_missing_tool_and_bad_arguments_are_safe(config):
    with pytest.raises(McpError):
        await McpClient().call_tool(config, "missing", {"a": 2})
    with pytest.raises(McpError) as error:
        await McpClient().call_tool(config, "add_numbers", [])
    assert error.value.code == "MCP_TOOL_ARGUMENTS_INVALID"
