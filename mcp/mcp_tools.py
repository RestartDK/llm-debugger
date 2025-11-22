"""
MCP tool functions for the debug context server.
"""
import json
from typing import Optional
from datetime import datetime
from storage import (
    read_json_file,
    write_json_file,
    append_to_json_file,
    CODE_CHUNKS_FILE,
    CHANGES_HISTORY_FILE,
    PROJECT_CONTEXT_FILE
)
from models import ChangeSubmission, CodeChunk
from extractors import validate_change_submission, extract_relational_context


def submit_code_changes(
    format_type: str = "structured",
    content: str = "",
    file_path: Optional[str] = None,
    line_numbers: Optional[str] = None,
    relationships: Optional[str] = None
) -> str:
    """
    Submit code changes for debugging context.
    Accepts code changes in diff or structured JSON format.
    
    Args:
        format_type: "diff" or "structured"
        content: Code change content (diff string or JSON string)
        file_path: File path (for structured format)
        line_numbers: JSON string with start/end line numbers
        relationships: JSON string with relationship data
    """
    try:
        # Parse JSON strings if provided
        content_obj = content
        if isinstance(content, str):
            try:
                content_obj = json.loads(content)
            except json.JSONDecodeError:
                content_obj = content
        
        line_nums = None
        if line_numbers:
            try:
                line_nums = json.loads(line_numbers)
            except json.JSONDecodeError:
                pass
        
        rels = None
        if relationships:
            try:
                rels = json.loads(relationships)
            except json.JSONDecodeError:
                pass
        
        submission = ChangeSubmission(
            format_type=format_type,
            content=content_obj,
            file_path=file_path,
            line_numbers=line_nums,
            relationships=rels
        )
        
        validated = validate_change_submission(submission)
        
        # Store change
        change = {
            **validated,
            "timestamp": datetime.now().isoformat()
        }
        append_to_json_file(CHANGES_HISTORY_FILE, change)
        
        # If structured format with code content, also store as code chunk
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
        
        return json.dumps({"status": "success", "message": "Code changes submitted successfully"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def get_project_context() -> str:
    """
    Returns project metadata and high-level summary.
    """
    context = read_json_file(PROJECT_CONTEXT_FILE, default={})
    return json.dumps(context)


def get_code_chunk_context(
    file_path: str,
    line_numbers: Optional[str] = None
) -> str:
    """
    Returns debugging context for specific code chunks with full relational info.
    
    Args:
        file_path: Path to the file
        line_numbers: JSON string with start/end line numbers (optional)
    """
    try:
        line_nums = None
        if line_numbers:
            line_nums = json.loads(line_numbers)
        
        chunks = read_json_file(CODE_CHUNKS_FILE, default=[])
        
        # Filter chunks by file_path
        matching_chunks = [c for c in chunks if c.get("file_path") == file_path]
        
        # Filter by line numbers if provided
        if line_nums:
            start = line_nums.get("start", 0)
            end = line_nums.get("end", 0)
            matching_chunks = [
                c for c in matching_chunks
                if (c.get("line_numbers", {}).get("start", 0) <= end and
                    c.get("line_numbers", {}).get("end", 0) >= start)
            ]
        
        return json.dumps({
            "file_path": file_path,
            "chunks": matching_chunks,
            "count": len(matching_chunks)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_mcp_documentation() -> str:
    """
    Returns documentation explaining available endpoints and tools.
    """
    doc = {
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
    return json.dumps(doc, indent=2)

