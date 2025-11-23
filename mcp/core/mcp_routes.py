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
from .create_ctrlflow_json import generate_code_graph_from_context

# Store active SSE connections and pending responses
sse_connections: Dict[str, deque] = {}


def send_progress_update(
    connection_id: Optional[str],
    stage: str,
    message: str,
    progress: float
) -> None:
    """
    DEPRECATED: Send progress update via SSE if connection available.
    
    This function is deprecated. Use FastMCP's ctx.report_progress() instead
    for progress reporting in MCP tools. This function is kept for backward
    compatibility with non-MCP code paths.
    
    Args:
        connection_id: SSE connection ID (if None, update is ignored)
        stage: Current stage identifier (e.g., "creating_nodes", "creating_edges")
        message: Human-readable progress message
        progress: Progress value between 0.0 and 1.0
    """
    logger_instance = logging.getLogger(__name__)
    logger_instance.warning("send_progress_update() is deprecated. Use FastMCP's ctx.report_progress() instead.")
    
    if not connection_id or connection_id not in sse_connections:
        # No connection available, just log
        logger_instance.debug(f"Progress update (no connection): {stage} - {message} ({progress:.1%})")
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
    logger_instance.info(f"Progress update queued for connection {connection_id}: {stage} - {message} ({progress:.1%})")


def get_tools_list_schema() -> dict:
    """Get the tools/list schema for MCP protocol."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "submit_code_context_mcp",
                    "description": (
                        "Submit ALL potential bug areas (multiple code chunks) discovered when investigating a user-reported issue. "
                        "For EVERY chunk include, in order: [Code Chunk N] with actual source (5-10 lines, no paraphrasing), "
                        "File: <filepath>, Lines: <start>-<end> (dash format), [Explanation] describing what bug this chunk can cause "
                        "and which related chunks look problematic vs. good, and [Relationships] describing only structural/logical/data-flow "
                        "links. Relationships MUST embed the actual related code (5-10 lines) plus its file path and line range—"
                        "never summarize in prose. Repeat this entire block for each chunk so the tool call contains multiple code chunks."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": (
                                    "Raw text payload that repeats the REQUIRED format for MULTIPLE code chunks: "
                                    "[Code Chunk N] with real source code (5-10 lines, copy directly from file), "
                                    "File: <filepath>, Lines: <start>-<end> (dash format), "
                                    "[Explanation] describing the possible bug and identifying which related chunks are problematic vs. good, "
                                    "[Relationships] describing structural/logical/data-flow links ONLY and embedding the actual code from "
                                    "those related chunks (include file path + line range). Provide ALL candidate chunks discovered during the "
                                    "bug investigation in ONE tool call. No English-only descriptions—every chunk and relationship must include code."
                                )
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
    logger_instance = logging.getLogger(__name__)
    
    connection_id = request.query_params.get("connection_id") or str(uuid.uuid4())
    response_queue = deque()
    sse_connections[connection_id] = response_queue
    
    logger_instance.info(f"New SSE connection established: {connection_id}")
    logger_instance.info(f"Client IP: {request.client.host if request.client else 'unknown'}")
    logger_instance.info(f"User-Agent: {request.headers.get('user-agent', 'unknown')}")
    
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
    logger_instance = logging.getLogger(__name__)
    
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        # Get connection ID from multiple possible sources (in order of preference)
        # 1. X-Connection-ID header (standard MCP SSE pattern)
        # 2. connection_id query parameter
        # 3. connection_id in request body (some clients send it here)
        # 4. Cookie-based tracking (if set during SSE connection)
        connection_id = (
            request.headers.get("x-connection-id") or 
            request.headers.get("X-Connection-ID") or
            request.query_params.get("connection_id") or
            body.get("connection_id") or
            body.get("params", {}).get("connection_id") or
            request.cookies.get("mcp_connection_id")
        )
        
        # Log connection_id extraction attempt for debugging
        logger_instance.info(f"MCP request received - method: {method}")
        logger_instance.debug(f"Request headers: {dict(request.headers)}")
        logger_instance.debug(f"Request query params: {dict(request.query_params)}")
        logger_instance.info(f"Extracted connection_id: {connection_id}")
        
        # Fallback: If no connection_id found, try to use the first available connection
        # This is a fallback for clients (like Cursor) that don't send connection_id
        # In production with multiple clients, this should be more sophisticated
        if not connection_id and sse_connections:
            # Use the first available connection (works for single-client scenarios)
            connection_id = list(sse_connections.keys())[0]
            logger_instance.warning(f"No connection_id in request, using first available connection: {connection_id}")
            logger_instance.warning("Consider implementing IP/session-based connection tracking for multi-client support")
        
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
        logger_instance = logging.getLogger(__name__)
        logger_instance.info(f"Stored connection_id {connection_id} in thread-local storage for MCP request")
    else:
        logger_instance = logging.getLogger(__name__)
        logger_instance.warning("No connection_id provided for MCP request - progress updates may not work")
        
        # Handle MCP tool call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            
        logger_instance.info(f"Processing tool call: {tool_name} with args keys: {list(tool_args.keys())}")
        
        # Try to use FastMCP's tool execution method if available
        if mcp_instance and hasattr(mcp_instance, '_tool_manager'):
            tool_manager = mcp_instance._tool_manager
            # Check if tool exists in tool manager
            tool_exists = False
            if hasattr(tool_manager, 'tools') and tool_name in tool_manager.tools:
                tool_exists = True
            elif hasattr(mcp_instance, 'get_tool'):
                tool_obj = mcp_instance.get_tool(tool_name)
                tool_exists = tool_obj is not None
            
            if tool_exists:
                logger_instance.info(f"Using FastMCP tool execution for {tool_name}")
                try:
                    # Get the tool object from tool manager
                    tool_obj = None
                    if hasattr(tool_manager, 'tools') and tool_name in tool_manager.tools:
                        tool_obj = tool_manager.tools[tool_name]
                    elif hasattr(mcp_instance, 'get_tool'):
                        tool_obj = mcp_instance.get_tool(tool_name)
                    
                    if tool_obj:
                        # Extract underlying function from FunctionTool wrapper
                        tool_func = None
                        if hasattr(tool_obj, 'fn'):
                            # FunctionTool wrapper has .fn attribute with the actual function
                            tool_func = tool_obj.fn
                        elif hasattr(tool_obj, 'function'):
                            tool_func = tool_obj.function
                        elif callable(tool_obj) and not isinstance(tool_obj, type):
                            # It's already a callable function
                            tool_func = tool_obj
                        
                        if tool_func:
                            logger_instance.info(f"Extracted function from tool wrapper: {tool_func}")
                            import inspect
                            # Handle both sync and async functions
                            if inspect.iscoroutinefunction(tool_func):
                                logger_instance.info(f"Calling async tool {tool_name}")
                                result = await tool_func(**tool_args)
                            else:
                                logger_instance.info(f"Calling synchronous tool {tool_name} - this will block until complete")
                                result = tool_func(**tool_args)
                            logger_instance.info(f"Tool {tool_name} completed with result length: {len(str(result))}")
                            return {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "content": [{"type": "text", "text": str(result)}]
                                }
                            }
                        else:
                            logger_instance.warning(f"Could not extract function from tool wrapper, trying _call_tool_mcp()")
                            # Fallback: try _call_tool_mcp if available
                            if hasattr(mcp_instance, '_call_tool_mcp'):
                                logger_instance.info(f"Calling tool {tool_name} via _call_tool_mcp()")
                                result = await mcp_instance._call_tool_mcp(tool_name, tool_args)
                                return {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "result": {
                                        "content": [{"type": "text", "text": str(result)}]
                                    }
                                }
                    else:
                        logger_instance.warning(f"Tool object not found, falling back to manual handler")
                except Exception as e:
                    logger_instance.error(f"FastMCP tool execution failed for {tool_name}: {str(e)}", exc_info=True)
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32603, "message": f"Tool execution error: {str(e)}"}
                    }
        
        logger_instance.warning(f"FastMCP tool discovery failed for {tool_name}. mcp_instance={mcp_instance is not None}, has_tool_manager={hasattr(mcp_instance, '_tool_manager') if mcp_instance else False}")
        
        # Manual tool handling (fallback if FastMCP discovery fails)
        # Try to use FastMCP's execution method even in fallback
        if tool_name == "submit_code_context_mcp":
            text = tool_args.get("text", "")
            if not text:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing required parameter: text"}
                }
            try:
                # Try to extract and call the function directly from tool manager
                if mcp_instance and hasattr(mcp_instance, '_tool_manager'):
                    tool_manager = mcp_instance._tool_manager
                    tool_obj = None
                    if hasattr(tool_manager, 'tools') and tool_name in tool_manager.tools:
                        tool_obj = tool_manager.tools[tool_name]
                    elif hasattr(mcp_instance, 'get_tool'):
                        tool_obj = mcp_instance.get_tool(tool_name)
                    
                    if tool_obj:
                        # Extract underlying function from FunctionTool wrapper
                        tool_func = None
                        if hasattr(tool_obj, 'fn'):
                            tool_func = tool_obj.fn
                        elif hasattr(tool_obj, 'function'):
                            tool_func = tool_obj.function
                        elif callable(tool_obj) and not isinstance(tool_obj, type):
                            tool_func = tool_obj
                        
                        if tool_func:
                            logger_instance.info(f"Extracted function from tool wrapper in fallback, calling directly")
                            import inspect
                            if inspect.iscoroutinefunction(tool_func):
                                result = await tool_func(**tool_args)
                            else:
                                result = tool_func(**tool_args)
                            return {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {
                                    "content": [{"type": "text", "text": str(result)}]
                                }
                            }
                
                # Last resort: call generate_code_graph_from_context directly
                # This ensures the graph generation always happens even if tool extraction fails
                logger_instance.warning("Calling generate_code_graph_from_context directly (same function the tool calls)")
                result = generate_code_graph_from_context(text)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result)}]
                    }
                }
            except Exception as e:
                logger_instance.error(f"Error in manual tool handler for {tool_name}: {str(e)}", exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Tool execution error: {str(e)}"}
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
        # Try to use FastMCP's tool discovery if available
        if mcp_instance and hasattr(mcp_instance, '_tool_manager'):
            import inspect
            tools = []
            tool_manager = mcp_instance._tool_manager
            
            # Get tools from tool manager
            tool_dict = {}
            if hasattr(tool_manager, 'tools'):
                tool_dict = tool_manager.tools
            elif hasattr(mcp_instance, 'get_tools'):
                tool_dict = mcp_instance.get_tools()
            
            for tool_name, tool_obj in tool_dict.items():
                # Extract underlying function from FunctionTool wrapper
                tool_func = tool_obj
                if hasattr(tool_obj, 'fn'):
                    # FunctionTool wrapper has .fn attribute with the actual function
                    tool_func = tool_obj.fn
                elif hasattr(tool_obj, 'function'):
                    tool_func = tool_obj.function
                elif callable(tool_obj) and not isinstance(tool_obj, type):
                    # It's already a callable function
                    tool_func = tool_obj
                
                # Get function signature and docstring
                sig = inspect.signature(tool_func)
                doc = inspect.getdoc(tool_func) or ""
                
                # Extract description from docstring
                # Include full docstring up to a reasonable limit for MCP protocol
                # This ensures all instructions and requirements are visible to the LLM
                if doc:
                    # Use the full docstring, but limit to 5000 chars to avoid overly long descriptions
                    # Most MCP clients can handle this length, and it ensures complete instructions
                    description = doc[:5000] + "..." if len(doc) > 5000 else doc
                else:
                    description = f"Tool: {tool_name}"
                
                # Build input schema from function parameters
                properties = {}
                required = []
                for param_name, param in sig.parameters.items():
                    # Skip 'self' and other special parameters
                    if param_name == 'self':
                        continue
                    
                    # Determine parameter type
                    param_type = "string"  # default
                    if param.annotation != inspect.Parameter.empty:
                        if param.annotation == int:
                            param_type = "integer"
                        elif param.annotation == float:
                            param_type = "number"
                        elif param.annotation == bool:
                            param_type = "boolean"
                        elif param.annotation == list:
                            param_type = "array"
                    
                    # Create parameter description
                    # For 'text' parameter, provide a helpful description
                    if param_name == "text":
                        param_description = "Raw text payload containing code chunks with format: [Code Chunk N], File, Lines, [Explanation], [Relationships]. See tool description for full format requirements."
                    else:
                        param_description = f"Parameter: {param_name}"
                    
                    properties[param_name] = {
                        "type": param_type,
                        "description": param_description
                    }
                    
                    # Add to required if no default value
                    if param.default == inspect.Parameter.empty:
                        required.append(param_name)
                
                tools.append({
                    "name": tool_name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required if required else []
                    }
                })
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools
                }
            }
        else:
            # Fall back to custom schema
            schema = get_tools_list_schema()
            schema["id"] = request_id
            return schema
        
    # Handle initialized notification (no response needed)
    elif method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": None}  # Notifications don't have responses
    
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

