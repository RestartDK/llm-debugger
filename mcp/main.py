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
    Submit potential bug areas from codebase analysis. REQUIRES MULTIPLE CODE CHUNKS in sequence, each with ACTUAL CODE BLOCKS (5-10 lines), not English descriptions.
    
    WORKFLOW: When a user reports a bug/error, scan the codebase to identify potential bug areas related to the reported issue. Send ALL candidate code chunks in ONE tool call.
    
    Format: Repeat this pattern for EACH potential bug area found:
    1. [Code Chunk N] - Include ACTUAL CODE (5-10 lines) that could be causing the bug
    2. File: <filepath> - Full file path where this code exists
    3. Lines: <start>-<end> - Line number range using dash format (e.g., "10-25")
    4. [Explanation] - What specific bug this code chunk might cause AND indicate which related code chunks are problematic vs. which look good (use descriptive text)
    5. [Relationships] - Structural/logical/data flow relationships to other code chunks (calls, dependencies, data flow) WITHOUT error context
    
    Then continue with the next code chunk using the same pattern.
    
    CRITICAL REQUIREMENTS:
    - Scan codebase when user reports a bug/error to find related code
    - Include MULTIPLE code chunks (not just one) - send ALL potential bug areas in one tool call
    - Each chunk must have REAL, executable code blocks (5-10 lines)
    - Do NOT use English descriptions like "for loop that iterates" - show actual code
    - Include file path and line number range (dash format) for each chunk
    - Explanation must describe what bug might occur AND indicate which related chunks are problematic vs. good
    - Relationships should be structural/logical/data flow only (no error context)
    
    Example format (showing MULTIPLE chunks):
    
    [Code Chunk 1]
    File: src/utils.py
    Lines: 15-24
    
    def process_data(items):
        result = []
        for item in items:
            if item is None:
                continue
            result.append(item * 2)
        return result
    
    [Explanation]
    This function doesn't handle the case where items is None or empty, which could cause a TypeError when iterating. Code Chunk 2 (calculate_totals) is problematic because it calls this function without checking if data is None first. Code Chunk 3 (API handler) looks good as it validates input before calling calculate_totals.
    
    [Relationships]
    This function is called by calculate_totals() function (see Code Chunk 2). The result is used by the API handler in Code Chunk 3. Receives data from the request processing pipeline.
    
    [Code Chunk 2]
    File: src/calculations.py
    Lines: 8-12
    
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
    [Explanation]
    This function calls process_data() without validating that data is None first, which will cause a TypeError. Code Chunk 1 (process_data) is problematic because it doesn't handle None input. Code Chunk 3 (API handler) looks good as it validates input.
    
    [Relationships]
    Calls process_data() from Code Chunk 1. Called by API handler in Code Chunk 3. Part of the data processing pipeline.
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
