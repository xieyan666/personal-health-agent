import asyncio
import socket
import subprocess
import sys
import pytest

from backend.app.mcp import McpClient, parse_server_config


async def _wait_port(host: str, port: int) -> None:
    for _ in range(60):
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError("HTTP MCP test server did not start")


@pytest.mark.asyncio
async def test_streamable_http_list_and_call_real_server():
    process = subprocess.Popen([sys.executable, "backend/tests/mcp/fixtures/http_server.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await _wait_port("127.0.0.1", 8765)
        config = parse_server_config({"transport": "streamable_http", "url": "http://127.0.0.1:8765/mcp", "allow_private_network": True})
        client = McpClient()
        tools = await client.list_tools(config)
        assert any(tool.name == "add_numbers" for tool in tools)
        result = await client.call_tool(config, "add_numbers", {"a": 2, "b": 3})
        assert result.success is True and "5" in result.content
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
