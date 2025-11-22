"""
MCP protocol route handlers (SSE endpoints).
"""
import json
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


def get_tools_list_schema() -> dict:
    """Get the tools/list schema for MCP protocol."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "submit_code_context_mcp",
                    "description": "Submit code changes with context. Send a text message containing: 1. Code chunks showing what changed (before/after), 2. Explanation of what the code does, 3. How this code relates to other code chunks. Example format: [Code Chunk] Changed: for i in range(10) To: for var in list [Explanation] This code iterates... [Relationships] This code relates to process_data()...",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Raw text containing code chunks, explanations, and relationships"
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


async def sse_message_handler(request: Request) -> dict:
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
        
        # Process the request and get response
        response = await process_mcp_request(method, params, request_id)
        
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


async def process_mcp_request(method: str, params: dict, request_id: Optional[int]) -> dict:
    """Process an MCP request and return the response."""
    # Handle MCP tool call
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
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
                    "tools": {}
                },
                "serverInfo": {
                    "name": "Debug Context MCP Server",
                    "version": "0.1.0"
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

