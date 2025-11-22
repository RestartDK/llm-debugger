"""
MCP Debug Context Server
Accepts code changes from Cursor, stores project context and code chunk debugging information.
Can be run as an MCP server (stdio) or as a FastAPI HTTP server with SSE support.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

# Import from core package
from core import (
    sse_endpoint_handler,
    sse_message_handler,
    submit_code_context
)

# Initialize the MCP server (for stdio mode)
mcp = FastMCP("Debug Context MCP Server")

# Register MCP tool
@mcp.tool()
def submit_code_context_mcp(text: str) -> str:
    """
    Submit code changes with context. Send a text message containing:
    1. Code chunks showing what changed (before/after)
    2. Explanation of what the code does
    3. How this code relates to other code chunks
    
    Example format:
    [Code Chunk]
    Changed: for i in range(10)
    To: for var in list
    
    [Explanation]
    This code iterates over a list and processes each item...
    
    [Relationships]
    This code relates to process_data() function by calling it for each item...
    """
    return submit_code_context(text)

# Create FastAPI app
app = FastAPI(title="Debug Context MCP Server", description="MCP server for code debugging context")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# REST API Routes
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "message": "Debug Context MCP Server",
        "version": "0.2.0",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "sse_message": "/sse/message"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Debug Context MCP Server"}



# ============================================================================
# MCP Protocol Routes (SSE)
# ============================================================================

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol over HTTP (GET for SSE stream)."""
    return await sse_endpoint_handler(request)


@app.post("/sse")
async def sse_post_endpoint(request: Request):
    """Handle POST requests to /sse endpoint (Cursor may POST here for messages)."""
    # Forward POST requests to the message handler
    return await sse_message_handler(request, mcp_instance=mcp)


@app.options("/sse")
async def sse_options():
    """Handle CORS preflight for SSE endpoint."""
    from fastapi.responses import Response
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/sse/message")
async def sse_message_options():
    """Handle CORS preflight for SSE message endpoint."""
    from fastapi.responses import Response
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.post("/sse/message")
async def sse_message_endpoint(request: Request):
    """Handle POST requests for MCP protocol messages.
    
    For SSE transport: responses are queued and sent via the SSE stream.
    For direct HTTP: responses are returned directly.
    """
    return await sse_message_handler(request, mcp_instance=mcp)


if __name__ == "__main__":
    import sys
    import uvicorn
    
    # Check if running in stdio mode (for MCP) or HTTP mode
    # If stdin is a TTY, run HTTP server; otherwise run stdio MCP server
    if sys.stdin.isatty():
        # Running interactively - start HTTP server
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        # Running via stdio (for Cursor MCP) - run MCP server
        mcp.run()
