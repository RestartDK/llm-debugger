"""
MCP Debug Context Server
Accepts code changes from Cursor, stores project context and code chunk debugging information.
Can be run as an MCP server (stdio) or as a FastAPI HTTP server with SSE support.
"""

import asyncio
import json
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import from core package
from core import sse_message_handler, submit_code_context
from core.create_ctrlflow_json import generate_code_graph_from_context

# Import from api package
from api import get_control_flow_diagram, execute_test_cases, send_debugger_response

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
    context_size = len(text or "")
    logger.info(
        "Graph generation request received (chars=%d). Running synchronously.",
        context_size,
    )
    
    try:
        result = generate_code_graph_from_context(text)
        
        logger.info(
            "Graph generation complete: status=%s filename=%s nodes=%s edges=%s",
            result.get("status"),
            result.get("filename"),
            result.get("nodes_count"),
            result.get("edges_count"),
        )

        # TODO: Add workflow orchestration functionality here
        # - Trigger UI updates
        # - Notify other services
        # - Handle graph processing pipeline

        # Return final result - tool will not return until graph generation is complete
        return json.dumps(result)
    except Exception as e:
        error_msg = f"Error generating graph: {str(e)}"
        logger.error(
            "Graph generation worker failed (chars=%d): %s",
            context_size,
            error_msg,
            exc_info=True,
        )

        return json.dumps({
            "status": "error",
            "message": error_msg
        })

# Create FastAPI app
app = FastAPI(
    title="Debug Context MCP Server",
    description="MCP server for code debugging context",
)

# Add CORS middleware
# Allow all origins for development (Vite dev server typically runs on localhost:5173)
# In production, replace "*" with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins - suitable for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
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
            "sse_message": "/sse/message",
        },
    }


@app.head("/")
async def root_head():
    """HEAD variant of root endpoint for health checks."""
    return JSONResponse(status_code=200, content=None)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Debug Context MCP Server"}


@app.get("/get_control_flow_diagram")
async def get_control_flow_diagram_endpoint():
    """Return the latest control-flow graph snapshot.

    Uses the dummy ecommerce pipeline until real projects are wired in, but
    the response already matches the frontend's Node<CfgNodeData>/Edge types.
    """
    logger.info("GET /get_control_flow_diagram - Building CFG via dummy pipeline")
    # Run the synchronous function in a thread pool to avoid event loop conflicts
    # This is necessary because get_control_flow_diagram() calls agent.run_sync()
    # which tries to use run_until_complete() on an already-running event loop
    diagram = await asyncio.to_thread(get_control_flow_diagram)
    logger.info(
        "GET /get_control_flow_diagram - nodes=%d edges=%d",
        len(diagram.get("nodes", [])),
        len(diagram.get("edges", [])),
    )
    return diagram


@app.post("/execute_test_cases")
async def execute_test_cases_endpoint(request: Request):
    """Execute test cases."""
    try:
        data = await request.json()
        logger.info(f"POST /execute_test_cases - Received: {data}")
        # Run the synchronous function in a thread pool to avoid event loop conflicts
        # This is necessary because execute_test_cases() calls agent.run_sync()
        result = await asyncio.to_thread(execute_test_cases, data)
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
        # Run the synchronous function in a thread pool to avoid event loop conflicts
        # This prevents issues if send_debugger_response() uses any blocking operations
        result = await asyncio.to_thread(send_debugger_response, data)
        logger.info(f"POST /send_debugger_response - Response: {result}")
        return result
    except Exception as e:
        logger.error(f"POST /send_debugger_response - Error: {str(e)}")
        return {"error": str(e)}


# ============================================================================
# MCP Protocol - SSE transport
# ============================================================================


@app.get("/sse")
async def sse_stream(request: Request):
    """Establish an SSE stream and return a connection_id."""
    connection_id = uuid.uuid4().hex
    logger.info("New SSE connection: %s", connection_id)
    async def event_generator():
        # Initial event so clients learn the connection_id
        yield (
            "event: mcp-connection\n"
            f"data: {json.dumps({'connection_id': connection_id})}\n\n"
        )
        try:
            while True:
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            logger.info("SSE connection %s cancelled by client", connection_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "X-Connection-ID": connection_id,
    }
    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=headers
    )


@app.post("/sse")
async def sse_post(request: Request):
    """Compatibility handler for clients that POST to /sse instead of /sse/message."""
    logger.info("POST /sse - forwarding payload to /sse/message handler")
    return await sse_message(request)


@app.post("/sse/message")
async def sse_message(request: Request):
    """Handle MCP JSON-RPC messages sent over HTTP and echo them to the SSE stream."""
    payload = await request.json()
    connection_id = (
        payload.get("connection_id")
        or payload.get("params", {}).get("connection_id")
        or request.headers.get("x-connection-id")
        or request.headers.get("X-Connection-ID")
        or request.query_params.get("connection_id")
        or request.cookies.get("mcp_connection_id")
    )
    if not connection_id:
        logger.warning("SSE message received without connection_id: %s", payload)

    result = await sse_message_handler(request, mcp_instance=mcp)

    return JSONResponse(result)


@app.options("/sse")
async def sse_options():
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
    from fastapi.responses import Response

    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


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
