import time
from fastmcp import FastMCP
from starlette.responses import JSONResponse
# Initialize MCP server
mcp = FastMCP(
    "test",
    instructions="""Say hello to the user by name."""
)
# Health check route
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "service": "company-intelligence",
        "version": "1.0.0",
        "timestamp": time.time(),
    })
@mcp.custom_route("/mcp/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "service": "company-intelligence",
        "version": "1.0.0",
        "timestamp": time.time(),
    })
@mcp.tool()
def hello_world() -> str:
    """Return a hello world message."""
    return "Hello, world!"
# Entry point
if __name__ == "__main__":
    # Launch server on localhost:8000 (default)
    mcp.run(transport="streamable-http", port=8080)