import os

import pytest

from backend.app.mcp import McpError, parse_server_config, resolve_env_reference


def test_valid_stdio_and_secret_resolution():
    config = parse_server_config({"transport": "stdio", "command": "python", "args": ["server.py"], "env": {"TOKEN": "env:TOKEN"}}, environment={"TOKEN": "secret"})
    assert config.command == "python" and config.args == ["server.py"] and config.env == {"TOKEN": "secret"}


@pytest.mark.parametrize("value", [{}, {"transport": "http", "command": "python"}, {"transport": "stdio"}, {"transport": "stdio", "command": "python", "args": "x"}, {"transport": "stdio", "command": "python", "args": [1]}])
def test_invalid_stdio_config(value):
    with pytest.raises(McpError):
        parse_server_config(value)


def test_missing_secret_is_safe_error():
    with pytest.raises(McpError) as error:
        resolve_env_reference("env:MISSING_4_6A", environment={})
    assert error.value.code == "MCP_CREDENTIAL_MISSING"
