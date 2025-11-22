"""
MCP Debug Context Server
Accepts code changes from Cursor, stores project context and code chunk debugging information.
Can be run as an MCP server (stdio) or as a FastAPI HTTP server with SSE support.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from typing import Optional

# Import route handlers
from api_routes import (
    submit_changes_handler,
    get_project_context_handler,
    get_chunk_context_handler,
    get_documentation
)
from mcp_routes import (
    sse_endpoint_handler,
    sse_message_handler
)
from models import ChangeSubmission, ChunkContextRequest
from mcp_tools import (
    submit_code_changes,
    get_project_context,
    get_code_chunk_context,
    get_mcp_documentation
)

# Initialize the MCP server (for stdio mode)
mcp = FastMCP("Debug Context MCP Server")

# Register MCP tools
@mcp.tool()
def submit_code_changes_mcp(
    format_type: str = "structured",
    content: str = "",
    file_path: Optional[str] = None,
    line_numbers: Optional[str] = None,
    relationships: Optional[str] = None
) -> str:
    """Submit code changes for debugging context."""
    return submit_code_changes(format_type, content, file_path, line_numbers, relationships)


@mcp.tool()
def get_project_context_mcp() -> str:
    """Returns project metadata and high-level summary."""
    return get_project_context()


@mcp.tool()
def get_code_chunk_context_mcp(
    file_path: str,
    line_numbers: Optional[str] = None
) -> str:
    """Returns debugging context for specific code chunks with full relational info."""
    return get_code_chunk_context(file_path, line_numbers)


@mcp.tool()
def get_mcp_documentation_mcp() -> str:
    """Returns documentation explaining available endpoints and tools."""
    return get_mcp_documentation()

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
        "version": "0.1.0",
        "endpoints": {
            "documentation": "/api/documentation",
            "project_context": "/api/project/context",
            "submit_changes": "/api/changes/submit",
            "chunk_context": "/api/debug/chunk-context",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Debug Context MCP Server"}


@app.post("/api/changes/submit")
async def submit_changes_endpoint(submission: ChangeSubmission):
    """Submit code changes (diff or structured JSON)."""
    return submit_changes_handler(submission)


@app.get("/api/project/context")
async def get_project_context_endpoint():
    """Get project context."""
    return get_project_context_handler()


@app.post("/api/debug/chunk-context")
async def get_chunk_context_endpoint(request: ChunkContextRequest):
    """Get code chunk debugging context."""
    return get_chunk_context_handler(request)


@app.get("/api/documentation")
async def get_documentation_endpoint():
    """Get MCP documentation."""
    return get_documentation()

# ============================================================================
# MCP Protocol Routes (SSE)
# ============================================================================

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol over HTTP."""
    return await sse_endpoint_handler(request)


@app.post("/sse/message")
async def sse_message_endpoint(request: Request):
    """Handle POST requests for MCP protocol messages."""
    return await sse_message_handler(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
