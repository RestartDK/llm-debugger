"""
MCP protocol route handlers (SSE endpoints).
"""
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio
from .mcp_tools import (
    submit_code_changes,
    get_project_context,
    get_code_chunk_context,
    get_mcp_documentation
)


def get_tools_list_schema() -> dict:
    """Get the tools/list schema for MCP protocol."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "submit_code_changes",
                    "description": "Submit code changes in diff or structured JSON format",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "format_type": {
                                "type": "string",
                                "description": "Format type: 'diff' or 'structured'",
                                "default": "structured"
                            },
                            "content": {
                                "type": "string",
                                "description": "Code change content (diff string or JSON string)"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "File path (for structured format)"
                            },
                            "line_numbers": {
                                "type": "object",
                                "description": "JSON object with start/end line numbers",
                                "properties": {
                                    "start": {"type": "integer"},
                                    "end": {"type": "integer"}
                                }
                            },
                            "relationships": {
                                "type": "object",
                                "description": "JSON object with relationship data"
                            }
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "get_project_context",
                    "description": "Returns project metadata and high-level summary",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_code_chunk_context",
                    "description": "Returns debugging context for specific code chunks with full relational info",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file"
                            },
                            "line_numbers": {
                                "type": "object",
                                "description": "JSON object with start/end line numbers",
                                "properties": {
                                    "start": {"type": "integer"},
                                    "end": {"type": "integer"}
                                }
                            }
                        },
                        "required": ["file_path"]
                    }
                },
                {
                    "name": "get_mcp_documentation",
                    "description": "Returns documentation explaining available endpoints and tools",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]
        }
    }


async def sse_endpoint_handler(request: Request) -> StreamingResponse:
    """SSE endpoint for MCP protocol over HTTP."""
    async def event_stream():
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(30)
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def sse_message_handler(request: Request) -> dict:
    """Handle POST requests for MCP protocol messages."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        # Handle MCP tool call
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            
            if tool_name == "submit_code_changes":
                result = submit_code_changes(
                    format_type=tool_args.get("format_type", "structured"),
                    content=json.dumps(tool_args.get("content", "")) if isinstance(tool_args.get("content"), dict) else str(tool_args.get("content", "")),
                    file_path=tool_args.get("file_path"),
                    line_numbers=json.dumps(tool_args.get("line_numbers")) if tool_args.get("line_numbers") else None,
                    relationships=json.dumps(tool_args.get("relationships")) if tool_args.get("relationships") else None
                )
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
                }
            
            elif tool_name == "get_project_context":
                result = get_project_context()
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
                }
            
            elif tool_name == "get_code_chunk_context":
                result = get_code_chunk_context(
                    file_path=tool_args.get("file_path", ""),
                    line_numbers=json.dumps(tool_args.get("line_numbers")) if tool_args.get("line_numbers") else None
                )
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
                }
            
            elif tool_name == "get_mcp_documentation":
                result = get_mcp_documentation()
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
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
        
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Unknown method"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32603, "message": str(e)}}

