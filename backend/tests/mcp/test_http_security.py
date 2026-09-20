import pytest
from backend.app.mcp import parse_server_config, McpError


@pytest.mark.parametrize("url", ["file:///tmp/mcp", "ftp://example.com/mcp", "ws://example.com/mcp", "https://user:pass@example.com/mcp", "http:///mcp"])
def test_http_url_validation_rejects_unsafe_forms(url):
    with pytest.raises(McpError) as exc:
        parse_server_config({"transport": "streamable_http", "url": url})
    assert exc.value.code == "MCP_HTTP_URL_INVALID"


@pytest.mark.parametrize("url", ["http://127.0.0.1:8765/mcp", "http://localhost:8765/mcp", "http://10.0.0.1/mcp"])
def test_http_private_addresses_are_rejected_by_default(url):
    with pytest.raises(McpError) as exc:
        parse_server_config({"transport": "streamable_http", "url": url})
    assert exc.value.code in {"MCP_HTTP_PRIVATE_ADDRESS_FORBIDDEN", "MCP_HTTP_HOST_RESOLUTION_FAILED"}


def test_http_local_development_switch_and_header_secret_resolution():
    config = parse_server_config({"transport": "streamable_http", "url": "http://127.0.0.1:8765/mcp", "allow_private_network": True, "headers": {"Authorization": "env:MCP_TOKEN"}}, environment={"MCP_TOKEN": "test-secret"})
    assert config.url.startswith("http://127.0.0.1")
    assert config.headers == {"Authorization": "test-secret"}


def test_http_missing_header_secret_is_safe():
    with pytest.raises(McpError) as exc:
        parse_server_config({"transport": "streamable_http", "url": "https://example.com/mcp", "headers": {"X-API-Key": "env:MISSING"}}, environment={})
    assert exc.value.code == "MCP_CREDENTIAL_MISSING"
    assert "env:" not in str(exc.value)
