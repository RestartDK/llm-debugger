"""
MCP protocol route handlers (SSE endpoints).
"""
import json
import logging
from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio
from typing import Dict, Optional
from collections import deque
from .mcp_tools import (
    submit_code_context
)

# Store active SSE connections and pending responses
sse_connections: Dict[str, deque] = {}


def send_progress_update(
    connection_id: Optional[str],
    stage: str,
    message: str,
    progress: float
) -> None:
    """
    Send progress update via SSE if connection available.
    
    Args:
        connection_id: SSE connection ID (if None, update is ignored)
        stage: Current stage identifier (e.g., "creating_nodes", "creating_edges")
        message: Human-readable progress message
        progress: Progress value between 0.0 and 1.0
    """
    if not connection_id or connection_id not in sse_connections:
        # No connection available, just log
        logger = logging.getLogger(__name__)
        logger.debug(f"Progress update (no connection): {stage} - {message} ({progress:.1%})")
        return
    
    progress_message = {
        "jsonrpc": "2.0",
        "method": "progress",
        "params": {
            "stage": stage,
            "message": message,
            "progress": progress
        }
    }
    
    sse_connections[connection_id].append(progress_message)


def get_tools_list_schema() -> dict:
    """Get the tools/list schema for MCP protocol."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "submit_code_context_mcp",
                    "description": "Submit potential bug areas from codebase analysis. When user reports a bug/error, scan codebase to identify potential bug areas and send ALL candidates in ONE tool call. REQUIRES SEQUENCE: [Code Chunk 1] with actual code (5-10 lines), File path, Lines range (dash format), [Explanation] (what bug + which related chunks are problematic vs. good), [Relationships] (structural/logical/data flow only, MUST include actual code from related chunks) → [Code Chunk 2] with same format → repeat. CRITICAL: Include MULTIPLE chunks, each with real executable code (not English descriptions). Relationships must show actual code from related chunks. Example: [Code Chunk 1] File: src/utils.py Lines: 15-24 def process_data(items): ... [Explanation] This function doesn't handle None input, which could cause TypeError. Code Chunk 2 is problematic because... [Relationships] Called by calculate_totals(). Related code: File: src/calc.py Lines: 8-12 def calculate_totals(data): ...",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Raw text containing MULTIPLE code chunks in sequence. Each chunk must have: [Code Chunk N] with actual code (5-10 lines), File: <filepath>, Lines: <start>-<end> (dash format), [Explanation] (what bug might occur + which related chunks are problematic vs. good), [Relationships] (structural/logical/data flow only, no error context, MUST include actual code from related chunks showing file path and line range). Repeat this pattern for each potential bug area. Must include real executable code blocks, not English descriptions. Send ALL potential bug areas in one tool call."
                            }
                        },
                        "required": ["text"]
                    }
                }
            ]
        }
    }


async def sse_endpoint_handler(request: Request) -> StreamingResponse:
    """SSE endpoint for MCP protocol over HTTP.
    
    This endpoint streams MCP protocol responses back to the client.
    Clients send requests via POST to /sse/message with X-Connection-ID header
    and receive responses via this SSE stream.
    """
    # Get or generate a connection ID
    import uuid
    connection_id = request.query_params.get("connection_id") or str(uuid.uuid4())
    response_queue = deque()
    sse_connections[connection_id] = response_queue
    
    async def event_stream():
        # Send initial connection message with connection ID
        yield f": connected\n\n"
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'connection', 'params': {'status': 'connected', 'connection_id': connection_id}})}\n\n"
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # Check for pending responses
                if response_queue:
                    response = response_queue.popleft()
                    yield f"data: {json.dumps(response)}\n\n"
                else:
                    # Send heartbeat every 30 seconds
                    await asyncio.sleep(30)
                    yield f": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up connection
            if connection_id in sse_connections:
                del sse_connections[connection_id]
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "X-Connection-ID": connection_id,  # Send connection ID in header
        }
    )


async def sse_message_handler(request: Request, mcp_instance=None) -> dict:
    """Handle POST requests for MCP protocol messages.
    
    Processes MCP JSON-RPC requests and returns responses.
    For SSE transport: if connection_id header is provided, response is also queued for SSE stream.
    """
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        # Get connection ID from header (Cursor may send this)
        connection_id = request.headers.get("x-connection-id") or request.query_params.get("connection_id")
        
        # Process the request and get response (pass connection_id for progress updates)
        response = await process_mcp_request(method, params, request_id, mcp_instance, connection_id=connection_id)
        
        # If we have a connection ID, also queue response for SSE stream
        if connection_id and connection_id in sse_connections:
            sse_connections[connection_id].append(response)
        
        # Always return response directly (standard HTTP POST behavior)
        return response
        
    except Exception as e:
        error_response = {"jsonrpc": "2.0", "id": body.get("id") if 'body' in locals() else None, "error": {"code": -32603, "message": str(e)}}
        connection_id = request.headers.get("x-connection-id") or request.query_params.get("connection_id")
        if connection_id and connection_id in sse_connections:
            sse_connections[connection_id].append(error_response)
        return error_response


async def process_mcp_request(method: str, params: dict, request_id: Optional[int], mcp_instance=None, connection_id: Optional[str] = None) -> dict:
    """Process an MCP request and return the response.
    
    Args:
        method: MCP method name
        params: Method parameters
        request_id: Request ID
        mcp_instance: Optional FastMCP instance for tool discovery
        connection_id: Optional SSE connection ID for progress updates
    """
    import threading
    
    # Store connection_id in thread-local storage so tools can access it
    if connection_id:
        threading.current_thread().mcp_connection_id = connection_id
    
    # Handle MCP tool call
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
        # Try to use FastMCP's tool if available, otherwise fall back to manual handling
        if mcp_instance and hasattr(mcp_instance, '_tools') and tool_name in mcp_instance._tools:
            try:
                tool_func = mcp_instance._tools[tool_name]
                result = tool_func(**tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": str(result)}]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Tool execution error: {str(e)}"}
                }
        
        # Manual tool handling (for SSE mode)
        if tool_name == "submit_code_context_mcp":
            text = tool_args.get("text", "")
            if not text:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing required parameter: text"}
                }
            result = submit_code_context(text)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }
    
    # Handle initialization
    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    }
                },
                "serverInfo": {
                    "name": "Debug Context MCP Server",
                    "version": "0.2.0"
                }
            }
        }
    
    # Handle tools/list
    elif method == "tools/list":
        schema = get_tools_list_schema()
        schema["id"] = request_id
        return schema
    
    # Handle initialized notification (no response needed)
    elif method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": None}  # Notifications don't have responses
    
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

