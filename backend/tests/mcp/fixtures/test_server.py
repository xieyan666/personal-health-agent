from mcp.server.fastmcp import FastMCP

mcp = FastMCP("4-6A test server")


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    mcp.run()
