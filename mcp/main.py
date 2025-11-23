"""
MCP Debug Context Server
Accepts code changes from Cursor, stores project context and code chunk debugging information.
Can be run as an MCP server (stdio) or as a FastAPI HTTP server with SSE support.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import from core package
from core import (
    sse_endpoint_handler,
    sse_message_handler,
    submit_code_context,
    send_progress_update
)
from core.create_ctrlflow_json import generate_code_graph_from_context

# Import from api package
from api import (
    get_control_flow_diagram,
    execute_test_cases,
    send_debugger_response
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
    5. [Relationships] - Structural/logical/data flow relationships to other code chunks (calls, dependencies, data flow) WITHOUT error context. MUST include the actual code from related chunks when referencing them (show the code, file path, and line range)
    
    Then continue with the next code chunk using the same pattern.
    
    CRITICAL REQUIREMENTS:
    - Scan codebase when user reports a bug/error to find related code
    - Include MULTIPLE code chunks (not just one) - send ALL potential bug areas in one tool call
    - Each chunk must have REAL, executable code blocks (5-10 lines)
    - Do NOT use English descriptions like "for loop that iterates" - show actual code
    - Include file path and line number range (dash format) for each chunk
    - Explanation must describe what bug might occur AND indicate which related chunks are problematic vs. good
    - Relationships should be structural/logical/data flow only (no error context)
    - Relationships MUST include actual code from related chunks when referencing them (show code, file path, and line range)
    
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
    
    Related code from Code Chunk 2:
    File: src/calculations.py
    Lines: 8-12
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
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
    
    Related code from Code Chunk 1:
    File: src/utils.py
    Lines: 15-24
    def process_data(items):
        result = []
        for item in items:
            if item is None:
                continue
            result.append(item * 2)
        return result
    """
    # Try to get connection_id from thread-local storage or context
    # For now, we'll attempt to get it but proceed even if None
    # Note: FastMCP tools don't have direct access to request context,
    # so connection_id may be None in stdio mode
    connection_id = getattr(threading.current_thread(), 'mcp_connection_id', None)
    
    if connection_id:
        logger.info(f"MCP tool called with connection_id: {connection_id}")
    else:
        logger.warning("MCP tool called without connection_id - progress updates will only be logged")
    
    # Create progress callback that sends SSE updates
    def progress_callback(stage: str, message: str, progress: float):
        send_progress_update(connection_id, stage, message, progress)
        logger.info(f"Progress: {stage} - {message} ({progress:.1%}) [connection_id: {connection_id}]")
    
    # Generate graph from context - this will block until complete
    # Progress updates will be sent via SSE during processing
    try:
        logger.info(f"Starting graph generation from MCP tool call [connection_id: {connection_id}]")
        result = generate_code_graph_from_context(
            text,
            progress_callback=progress_callback
        )
        logger.info(f"Graph generation complete: {result.get('status')}")
        
        # TODO: Add workflow orchestration functionality here
        # - Trigger UI updates
        # - Notify other services
        # - Handle graph processing pipeline
        
        # Return final result - tool will not return until graph generation is complete
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Error generating graph: {str(e)}"
        logger.error(error_msg)
        if connection_id:
            send_progress_update(connection_id, "error", error_msg, 0.0)
        return json.dumps({
            "status": "error",
            "message": error_msg
        })

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
            "get_control_flow_diagram": "/get_control_flow_diagram",
            "execute_test_cases": "/execute_test_cases",
            "send_debugger_response": "/send_debugger_response",
            "sse": "/sse",
            "sse_message": "/sse/message"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Debug Context MCP Server"}


@app.get("/get_control_flow_diagram")
async def get_control_flow_diagram_endpoint():
    """Get control flow diagram data."""
    try:
        result = get_control_flow_diagram()
        logger.info(f"GET /get_control_flow_diagram - Response: {result}")
        return result
    except Exception as e:
        logger.error(f"GET /get_control_flow_diagram - Error: {str(e)}")
        return {"error": str(e)}


@app.post("/execute_test_cases")
async def execute_test_cases_endpoint(request: Request):
    """Execute test cases."""
    try:
        data = await request.json()
        logger.info(f"POST /execute_test_cases - Received: {data}")
        result = execute_test_cases(data)
        logger.info(f"POST /execute_test_cases - Response: {result}")
        return result
    except Exception as e:
        logger.error(f"POST /execute_test_cases - Error: {str(e)}")
        return {"error": str(e)}


@app.post("/send_debugger_response")
async def send_debugger_response_endpoint(request: Request):
    """Send debugger response."""
    try:
        data = await request.json()
        logger.info(f"POST /send_debugger_response - Received: {data}")
        result = send_debugger_response(data)
        logger.info(f"POST /send_debugger_response - Response: {result}")
        return result
    except Exception as e:
        logger.error(f"POST /send_debugger_response - Error: {str(e)}")
        return {"error": str(e)}


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
