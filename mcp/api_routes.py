"""
REST API route handlers for the debug context server.
"""
from fastapi import HTTPException
from datetime import datetime
from storage import read_json_file, write_json_file, CODE_CHUNKS_FILE
from models import ChangeSubmission, ChunkContextRequest, CodeChunk
from extractors import validate_change_submission, extract_relational_context


def get_documentation() -> dict:
    """Get API documentation."""
    return {
        "server": "Debug Context MCP Server",
        "version": "0.1.0",
        "description": "MCP server for accepting code changes and providing debugging context",
        "mcp_tools": [
            {
                "name": "submit_code_changes",
                "description": "Submit code changes in diff or structured JSON format",
                "parameters": ["format_type", "content", "file_path", "line_numbers", "relationships"]
            },
            {
                "name": "get_project_context",
                "description": "Get project metadata and high-level summary",
                "parameters": []
            },
            {
                "name": "get_code_chunk_context",
                "description": "Get debugging context for specific code chunks",
                "parameters": ["file_path", "line_numbers"]
            },
            {
                "name": "get_mcp_documentation",
                "description": "Get this documentation",
                "parameters": []
            }
        ],
        "rest_endpoints": [
            {
                "method": "POST",
                "path": "/api/changes/submit",
                "description": "Submit code changes"
            },
            {
                "method": "GET",
                "path": "/api/project/context",
                "description": "Get project context"
            },
            {
                "method": "POST",
                "path": "/api/debug/chunk-context",
                "description": "Get code chunk debugging context"
            },
            {
                "method": "GET",
                "path": "/api/documentation",
                "description": "Get API documentation"
            }
        ]
    }


def submit_changes_handler(submission: ChangeSubmission) -> dict:
    """Submit code changes (diff or structured JSON)."""
    try:
        validated = validate_change_submission(submission)
        
        from storage import CHANGES_HISTORY_FILE, append_to_json_file
        
        change = {
            **validated,
            "timestamp": datetime.now().isoformat()
        }
        append_to_json_file(CHANGES_HISTORY_FILE, change)
        
        # Store as code chunk if structured format
        if validated["format_type"] == "structured" and isinstance(validated["content"], dict):
            code_content = validated["content"].get("code_content", validated["content"].get("old_code", "") or validated["content"].get("new_code", ""))
            if code_content and validated["file_path"]:
                chunk = CodeChunk(
                    file_path=validated["file_path"],
                    line_numbers=validated["line_numbers"] or {"start": 0, "end": 0},
                    code_content=code_content,
                    affected_files=validated["relationships"].get("affected_files", []),
                    **extract_relational_context(code_content, validated["file_path"])
                )
                chunks = read_json_file(CODE_CHUNKS_FILE, default=[])
                chunks.append(chunk.model_dump())
                write_json_file(CODE_CHUNKS_FILE, chunks)
        
        return {"status": "success", "message": "Code changes submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_project_context_handler() -> dict:
    """Get project context."""
    from storage import PROJECT_CONTEXT_FILE
    context = read_json_file(PROJECT_CONTEXT_FILE, default={})
    return context


def get_chunk_context_handler(request: ChunkContextRequest) -> dict:
    """Get code chunk debugging context."""
    try:
        chunks = read_json_file(CODE_CHUNKS_FILE, default=[])
        
        matching_chunks = [c for c in chunks if c.get("file_path") == request.file_path]
        
        if request.line_numbers:
            start = request.line_numbers.get("start", 0)
            end = request.line_numbers.get("end", 0)
            matching_chunks = [
                c for c in matching_chunks
                if (c.get("line_numbers", {}).get("start", 0) <= end and
                    c.get("line_numbers", {}).get("end", 0) >= start)
            ]
        
        return {
            "file_path": request.file_path,
            "chunks": matching_chunks,
            "count": len(matching_chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

