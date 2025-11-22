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
    Submit code changes with context. REQUIRES MULTIPLE CODE CHUNKS in sequence, each with ACTUAL CODE BLOCKS (5-10 lines), not English descriptions.
    
    Format: Repeat this pattern for EACH code chunk that changed:
    1. [Code Chunk] - Include ACTUAL CODE (5-10 lines) showing what changed, with clear BEFORE and AFTER blocks
    2. [Explanation] - Brief explanation of what this specific code chunk does
    3. [Relationships] - How this code chunk relates to OTHER code chunks (reference other chunks by name/file)
    
    Then continue with the next code chunk using the same pattern.
    
    CRITICAL REQUIREMENTS:
    - Include MULTIPLE code chunks (not just one)
    - Each chunk must have REAL, executable code blocks (5-10 lines)
    - Do NOT use English descriptions like "for loop that iterates" - show actual code
    - Each chunk should reference relationships to other chunks
    
    Example format (showing MULTIPLE chunks):
    
    [Code Chunk 1]
    File: src/utils.py
    
    BEFORE:
    def process_data(items):
        result = []
        for i in range(len(items)):
            item = items[i]
            result.append(item * 2)
        return result
    
    AFTER:
    def process_data(items):
        result = []
        for item in items:
            result.append(item * 2)
        return result
    
    [Explanation]
    Refactored the function to use direct iteration over items instead of index-based access, making the code more Pythonic and readable.
    
    [Relationships]
    This function is called by calculate_totals() function (see Code Chunk 2) and is used by the API endpoint in src/api/routes.py (see Code Chunk 3).
    
    [Code Chunk 2]
    File: src/calculations.py
    
    BEFORE:
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
    AFTER:
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
    [Explanation]
    This function calls process_data() from Code Chunk 1 to process the input data before calculating totals.
    
    [Relationships]
    Depends on process_data() function from Code Chunk 1. Called by the API handler in Code Chunk 3.
    
    [Code Chunk 3]
    File: src/api/routes.py
    
    BEFORE:
    @app.route('/api/totals')
    def get_totals():
        data = request.json
        totals = calculate_totals(data)
        return jsonify({'totals': totals})
    
    AFTER:
    @app.route('/api/totals')
    def get_totals():
        data = request.json
        totals = calculate_totals(data)
        return jsonify({'totals': totals})
    
    [Explanation]
    API endpoint that uses calculate_totals() from Code Chunk 2 to process requests.
    
    [Relationships]
    Calls calculate_totals() from Code Chunk 2, which in turn uses process_data() from Code Chunk 1.
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
