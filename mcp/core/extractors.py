"""
Relational context extraction and validation functions.
"""
import re
from typing import List, Dict, Any
from .models import ChangeSubmission


def extract_imports(code_content: str) -> List[str]:
    """Extract import statements from code."""
    imports = []
    # Match import statements (Python, JavaScript, TypeScript patterns)
    patterns = [
        r'^import\s+([^\s]+)',  # Python: import module
        r'^from\s+([^\s]+)\s+import',  # Python: from module import
        r'^import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',  # JS/TS: import ... from "..."
        r'^const\s+\w+\s*=\s*require\([\'"]([^\'"]+)[\'"]\)',  # JS: require()
    ]
    for line in code_content.split('\n'):
        for pattern in patterns:
            match = re.search(pattern, line.strip())
            if match:
                imports.append(match.group(1))
    return imports


def extract_function_definitions(code_content: str) -> List[str]:
    """Extract function definitions from code."""
    functions = []
    patterns = [
        r'^def\s+(\w+)\s*\(',  # Python: def function_name(
        r'^function\s+(\w+)\s*\(',  # JS: function function_name(
        r'^const\s+(\w+)\s*=\s*\(',  # JS: const function_name = (
        r'^(\w+)\s*:\s*function\s*\(',  # JS: name: function(
    ]
    for line in code_content.split('\n'):
        for pattern in patterns:
            match = re.search(pattern, line.strip())
            if match:
                functions.append(match.group(1))
    return functions


def extract_function_calls(code_content: str) -> List[str]:
    """Extract function calls from code."""
    calls = []
    # Simple pattern: word followed by (
    pattern = r'(\w+)\s*\('
    matches = re.findall(pattern, code_content)
    # Filter out common keywords
    keywords = {'if', 'for', 'while', 'with', 'def', 'class', 'return', 'print', 'len', 'str', 'int', 'list', 'dict'}
    calls = [m for m in matches if m not in keywords and not m[0].isdigit()]
    return list(set(calls))  # Remove duplicates


def extract_relational_context(code_content: str, file_path: str) -> Dict[str, Any]:
    """Extract relational context from code chunk."""
    imports = extract_imports(code_content)
    functions = extract_function_definitions(code_content)
    calls = extract_function_calls(code_content)
    
    return {
        "imports": imports,
        "callers": [],  # Would need full codebase analysis to determine
        "callees": calls,
        "data_flow_deps": []  # Would need static analysis
    }


def is_diff_format(content: str) -> bool:
    """Check if content is in diff format."""
    diff_indicators = ['---', '+++', '@@', '- ', '+ ']
    lines = content.split('\n')[:10]  # Check first 10 lines
    return any(indicator in line for line in lines for indicator in diff_indicators)


def validate_change_submission(submission: ChangeSubmission) -> Dict[str, Any]:
    """Validate and normalize change submission."""
    content = submission.content
    
    # Detect format if not specified
    if not submission.format_type or submission.format_type == "auto":
        if isinstance(content, str) and is_diff_format(content):
            submission.format_type = "diff"
        elif isinstance(content, dict):
            submission.format_type = "structured"
        else:
            submission.format_type = "structured"
    
    # Normalize structured format
    if submission.format_type == "structured" and isinstance(content, dict):
        # Extract file_path and line_numbers from structured content if not provided
        if not submission.file_path and "file_path" in content:
            submission.file_path = content["file_path"]
        if not submission.line_numbers and "line_numbers" in content:
            submission.line_numbers = content["line_numbers"]
    
    return {
        "format_type": submission.format_type,
        "content": content,
        "file_path": submission.file_path,
        "line_numbers": submission.line_numbers,
        "relationships": submission.relationships or {}
    }

