from mcp.server.fastmcp import FastMCP

mcp = FastMCP("4-6C HTTP test server")


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    mcp.settings.host = "127.0.0.1"
    mcp.settings.port = 8765
    mcp.run(transport="streamable-http")
