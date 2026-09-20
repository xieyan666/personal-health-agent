import pytest

from backend.app.mcp import McpError, parse_server_config


@pytest.mark.parametrize("command", ["cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "bash", "sh", "python && whoami", "python;whoami"])
def test_shell_commands_are_rejected(command):
    with pytest.raises(McpError) as error:
        parse_server_config({"transport": "stdio", "command": command})
    assert error.value.code == "MCP_CONFIG_INVALID"


def test_env_values_must_be_references():
    with pytest.raises(McpError):
        parse_server_config({"transport": "stdio", "command": "python", "env": {"TOKEN": "plain-secret"}})
