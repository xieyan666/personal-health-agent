from __future__ import annotations

import os
import re
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Any, Mapping

from backend.app.mcp.errors import *
from backend.app.mcp.types import McpServerConfig

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN = {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "bash", "sh"}


def resolve_env_reference(value: str, environment: Mapping[str, str] | None = None) -> str:
    if not isinstance(value, str) or not value.startswith("env:"):
        raise McpError(MCP_CONFIG_INVALID)
    name = value.removeprefix("env:")
    if not _ENV_NAME.fullmatch(name):
        raise McpError(MCP_CONFIG_INVALID)
    resolved = (environment or os.environ).get(name)
    if not resolved:
        raise McpError(MCP_CREDENTIAL_MISSING)
    return resolved


def parse_server_config(value: Mapping[str, Any], *, environment: Mapping[str, str] | None = None) -> McpServerConfig:
    if not isinstance(value, Mapping):
        raise McpError(MCP_CONFIG_INVALID)
    transport = value.get("transport")
    if transport not in {"stdio", "streamable_http"}:
        raise McpError(MCP_TRANSPORT_UNSUPPORTED)
    if transport == "streamable_http":
        url = value.get("url")
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise McpError(MCP_HTTP_URL_INVALID)
        allow_private = value.get("allow_private_network", False)
        if not isinstance(allow_private, bool):
            raise McpError(MCP_CONFIG_INVALID)
        if not allow_private:
            try:
                addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
            except OSError as exc:
                raise McpError(MCP_HTTP_HOST_RESOLUTION_FAILED) from exc
            for address in addresses:
                try:
                    ip = ipaddress.ip_address(address)
                except ValueError as exc:
                    raise McpError(MCP_HTTP_HOST_RESOLUTION_FAILED) from exc
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                    raise McpError(MCP_HTTP_PRIVATE_ADDRESS_FORBIDDEN)
        raw_headers = value.get("headers", {})
        if not isinstance(raw_headers, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in raw_headers.items()):
            raise McpError(MCP_CONFIG_INVALID)
        headers = {key: resolve_env_reference(ref, environment) for key, ref in raw_headers.items()}
        return McpServerConfig("streamable_http", "", [], {}, url=url, headers=headers, allow_private_network=allow_private)
    command = value.get("command")
    args = value.get("args", [])
    env = value.get("env", {})
    if not isinstance(command, str) or not command.strip() or command.lower() in _FORBIDDEN or any(token in command for token in ("&&", ";", "|", "\n", "\r")):
        raise McpError(MCP_CONFIG_INVALID)
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise McpError(MCP_CONFIG_INVALID)
    if not isinstance(env, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
        raise McpError(MCP_CONFIG_INVALID)
    resolved_env = {key: resolve_env_reference(ref, environment) for key, ref in env.items()}
    return McpServerConfig("stdio", command, list(args), resolved_env)
