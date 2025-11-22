"""
Core package for MCP Debug Context Server.
Exports all main components for easy importing.
"""
from .api_routes import (
    submit_changes_handler,
    get_project_context_handler,
    get_chunk_context_handler,
    get_documentation
)
from .mcp_routes import (
    sse_endpoint_handler,
    sse_message_handler
)
from .models import (
    ProjectContext,
    CodeChunk,
    CodeChange,
    ChangeSubmission,
    ChunkContextRequest
)
from .mcp_tools import (
    submit_code_changes,
    get_project_context,
    get_code_chunk_context,
    get_mcp_documentation
)
from .storage import (
    read_json_file,
    write_json_file,
    append_to_json_file,
    CODE_CHUNKS_FILE,
    CHANGES_HISTORY_FILE,
    PROJECT_CONTEXT_FILE
)
from .extractors import (
    extract_imports,
    extract_function_definitions,
    extract_function_calls,
    extract_relational_context,
    is_diff_format,
    validate_change_submission
)

__all__ = [
    # API Routes
    "submit_changes_handler",
    "get_project_context_handler",
    "get_chunk_context_handler",
    "get_documentation",
    # MCP Routes
    "sse_endpoint_handler",
    "sse_message_handler",
    # Models
    "ProjectContext",
    "CodeChunk",
    "CodeChange",
    "ChangeSubmission",
    "ChunkContextRequest",
    # MCP Tools
    "submit_code_changes",
    "get_project_context",
    "get_code_chunk_context",
    "get_mcp_documentation",
    # Storage
    "read_json_file",
    "write_json_file",
    "append_to_json_file",
    "CODE_CHUNKS_FILE",
    "CHANGES_HISTORY_FILE",
    "PROJECT_CONTEXT_FILE",
    # Extractors
    "extract_imports",
    "extract_function_definitions",
    "extract_function_calls",
    "extract_relational_context",
    "is_diff_format",
    "validate_change_submission",
]

