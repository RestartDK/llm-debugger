"""
Data models for the debug context server.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ProjectContext(BaseModel):
    """Project context model."""
    name: Optional[str] = None
    version: Optional[str] = None
    file_structure: Optional[List[str]] = []
    summary: Optional[str] = None
    entry_points: Optional[List[str]] = []
    dependencies: Optional[List[str]] = []


class CodeChunk(BaseModel):
    """Code chunk model with relational context."""
    file_path: str
    line_numbers: Dict[str, int] = Field(default_factory=lambda: {"start": 0, "end": 0})
    code_content: str
    affected_files: Optional[List[str]] = []
    imports: Optional[List[str]] = []
    callers: Optional[List[str]] = []
    callees: Optional[List[str]] = []
    data_flow_deps: Optional[List[str]] = []


class CodeChange(BaseModel):
    """Code change model."""
    format_type: str  # "diff" or "structured"
    content: str
    timestamp: str
    relationships: Optional[Dict[str, Any]] = {}


class ChangeSubmission(BaseModel):
    """Model for submitting code changes."""
    format_type: Optional[str] = "structured"  # "diff" or "structured"
    content: Any  # Can be string (diff) or dict (structured)
    file_path: Optional[str] = None
    line_numbers: Optional[Dict[str, int]] = None
    relationships: Optional[Dict[str, Any]] = {}


class ChunkContextRequest(BaseModel):
    """Request model for getting code chunk context."""
    file_path: str
    line_numbers: Optional[Dict[str, int]] = None

