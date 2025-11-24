"""
MCP Debug Context Server
Accepts code changes from Cursor, stores project context and code chunk debugging information.
Can be run as an MCP server (stdio) or as a FastAPI HTTP server with SSE support.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime

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
from api.debug_fix_instructions import get_most_recent_instructions

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

    IMPORTANT: This tool kicks off a LONG-RUNNING workflow that:
    1. Generates code nodes and edges using LLM calls (may take 30-60 seconds)
    2. Saves the control flow graph to a JSON file
    3. Makes it available via the GET endpoint for the frontend UI
    4. The frontend will display the graph and allow users to trigger test execution

    AFTER CALLING THIS TOOL:
    - DO NOT immediately call the next tool (fetch_instructions_from_debugger)
    - Return the frontend link to the user using the BUGPOINT_UI_URL environment variable
    - Tell the user to navigate to the UI to view the control flow diagram
    - End this session and wait for user interaction
    - The next tool call should only happen after the user has interacted with the UI and enough time has passed for the long-running workflow to complete

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

        # Format user-friendly response with frontend link
        if result.get("status") == "completed":
            nodes_count = result.get("nodes_count", 0)
            edges_count = result.get("edges_count", 0)
            filename = result.get("filename", "unknown")
            
            frontend_base_url = os.getenv("BUGPOINT_UI_URL") or ""

            response_message = f"""✅ Control flow graph generation completed successfully!

**Graph Summary:**
- Nodes: {nodes_count}
- Edges: {edges_count}
- Saved to: {filename}

🔗 **View the control flow diagram in the UI:**
{"[Open Debugger UI](" + frontend_base_url + ")" if frontend_base_url else "Open your configured debugger UI in the browser to view the control flow diagram."}

**Important:** This tool has kicked off a long-running workflow. The control flow graph is now being processed and will be available in the frontend UI. 

**Next Steps:**
1. Click the link above to navigate to the debugger UI
2. The UI will display the control flow diagram with code nodes and their relationships
3. You can interact with the diagram and trigger test execution from the UI
4. Wait for user interaction before proceeding with any additional tool calls

**Note:** Do not immediately call the next tool (fetch_instructions_from_debugger). End this session and wait for the user to interact with the UI. The next tool call should only happen after enough time has passed for the long-running workflow to complete and the user has had a chance to review the results."""
        else:
            # Error case
            error_msg = result.get("message", "Unknown error occurred")
            response_message = f"""❌ Error generating control flow graph: {error_msg}

The graph generation failed. Please check the error message above and try again."""
        
        return response_message
        
    except Exception as e:
        error_msg = f"Error generating graph: {str(e)}"
        logger.error(
            "Graph generation worker failed (chars=%d): %s",
            context_size,
            error_msg,
            exc_info=True,
        )

        return f"""❌ Error generating control flow graph: {error_msg}

An exception occurred during graph generation. Please check the error details and try again."""


# Register second MCP tool
@mcp.tool()
def fetch_instructions_from_debugger() -> str:
    """
    Fetch debugger fix instructions that have been generated by the debugging pipeline.

    This tool reads the file with the most recent timestamp from the instructions/ folder
    and returns the string contents of that text file to the coding agent.
    
    Files are named with the pattern YYYY-MM-DD_HH-MM.txt (e.g., "2025-11-23_14-30.txt").
    The tool automatically finds the most recent file by timestamp and returns its complete
    text contents as a string.

    Returns:
        str: The complete text contents of the most recent instruction file, or an error message
             if no file is found or cannot be read.
    """
    logger.info("Fetching debugger instructions")
    try:
        instructions = get_most_recent_instructions()
        logger.info(f"Retrieved instructions (length: {len(instructions)} chars)")
        return instructions
    except Exception as e:
        error_msg = f"Error fetching instructions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


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
def get_control_flow_diagram_endpoint():
    """Return the latest control-flow graph snapshot.

    Reads the most recent JSON file from the contexts/ folder that matches
    the timestamp pattern YYYY-MM-DD_HH-MM.json.
    The response matches the frontend's Node<CfgNodeData>/Edge types.
    """
    logger.info("GET /get_control_flow_diagram - Reading CFG from most recent context JSON")
    diagram = get_control_flow_diagram()
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
        # This prevents issues if execute_test_cases() or its dependencies use asyncio.run()
        result = await asyncio.to_thread(execute_test_cases, data)
        logger.info(f"POST /execute_test_cases - Response: {result}")
        
        # Save lessons learned and instructions to local storage
        try:
            # Extract final_analysis and build instruction content
            final_analysis = result.get("final_analysis", "")
            task_description = data.get("task_description", "Test execution results")
            
            # Only get relevant keys: analysis, attempts, final_analysis, and dump them as strings
            analysis_str = str(result.get("analysis"))
            attempts_str = str(result.get("attempts"))
            final_analysis_str = str(result.get("final_analysis"))

            # Write to .txt instructions for editing, summarizing the test results and actions
            instruction_content = "[Instructions for Edit]\n"
            instruction_content += "Make changes according to these testing results:\n"
            instruction_content += f"Analysis:\n{analysis_str}\n"
            instruction_content += f"Attempts:\n{attempts_str}\n"
            instruction_content += f"Final Analysis:\n{final_analysis_str if final_analysis_str else 'No final analysis available.'}\n"

            # Ensure instructions directory exists
            output_dir = "instructions"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp: YY-MM-DD_HH-MM.txt
            timestamp = datetime.now().strftime("%y-%m-%d_%H-%M")
            filename = f"{timestamp}.txt"
            filepath = os.path.join(output_dir, filename)

            # Write instruction file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(instruction_content)

            logger.info(f"POST /execute_test_cases - Saved instructions to {filepath}")
        except Exception as e:
            logger.error(f"POST /execute_test_cases - Failed to save instructions: {str(e)}")
        
        # Return the result regardless of whether instruction saving succeeded
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
