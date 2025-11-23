from __future__ import annotations

from textwrap import dedent
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class EnhancedSource(BaseModel):
    """
    Structured representation of an enhanced source code file.
    """

    file_path: str = Field(..., description="Original file path")
    enhanced_code: str = Field(..., description="Self-contained executable code with stubs/imports")
    added_imports: List[str] = Field(
        default_factory=list,
        description="List of imports or stubs that were added",
    )
    reasoning: str = Field(
        ..., description="Brief explanation of what was enhanced and why"
    )


def build_enhancement_prompt(
    code_snippet: str,
    file_path: str,
    error_context: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Build a prompt that asks the LLM to enhance code snippets to be self-contained and executable.
    """

    error_section = ""
    if error_context:
        error_details = []
        for err in error_context:
            error_type = err.get("error_type", "unknown")
            error_msg = err.get("message", "Unknown error")
            file_path_err = err.get("file_path", file_path)
            traceback = err.get("traceback", "")
            
            error_details.append(
                f"Error Type: {error_type}\n"
                f"Error Message: {error_msg}\n"
                f"File: {file_path_err}\n"
                f"Traceback:\n{traceback[:500] if traceback else 'N/A'}"
            )
        
        error_section = f"""
Previous Execution Errors:
{chr(10).join(error_details)}

The code failed to execute with the above errors. Please fix these specific issues.
"""

    prompt = f"""
You are a senior Python engineer tasked with making incomplete code snippets self-contained and executable.

Code snippet to enhance:
```python
{code_snippet.strip()}
```

File path: {file_path}
{error_section}

Your task:
1. Analyze the code to identify missing dependencies (imports, classes, enums, functions, constants, etc.)
2. Infer reasonable implementations based on how these dependencies are used in the code
3. Create minimal stubs or implementations that allow the code to execute
4. You MAY modify the code to make it standalone executable (e.g., removing external API calls, mocking complex logic). 
5. Add a 3-5 word comment (e.g., "# Mocking external dependency") wherever you add stubs or modify code to enable execution.
6. Add only the minimal necessary code to make it executable

Guidelines:
- If you see `Language.ROUND` or similar enum-like usage, create an Enum class with appropriate values
- If you see `@app.post` or similar decorators, these are already stubbed (FastAPI/Flask stubs exist)
- If a class/function is referenced but not defined, create a minimal stub that matches the usage pattern
- For imports, add standard library imports or create stub modules as needed
- For module-level constants, infer reasonable values based on usage
- You can remove logic that blocks execution (like network calls) and replace with mocks, adding a comment.
- Keep stubs minimal - they just need to allow execution, not be fully functional
- explicit instruction: "If you see an import or class that is not standard library, MOCK IT or stub it. Do not assume it exists."

Return the enhanced code that:
- Is self-contained and executable
- Includes all necessary imports/stubs at the top
- Can be executed without NameError, ImportError, or similar dependency errors

CRITICAL: You MUST provide structured output matching this exact JSON schema:
{{
  "file_path": "string (required - must match the provided file_path)",
  "enhanced_code": "string (required - complete executable Python code with imports/stubs)",
  "added_imports": ["array of strings (required - list of what was added, can be empty array [])"],
  "reasoning": "string (required - brief explanation of what was enhanced)"
}}

IMPORTANT STRUCTURED OUTPUT RULES:
- ALL required fields must be present and non-null
- "file_path" must be a string matching the provided file path
- "enhanced_code" must be a string containing the complete executable code
- "added_imports" must be an array of strings (can be empty [] if nothing was added)
- "reasoning" must be a string explaining what was enhanced
- Ensure all fields match their schema types exactly: strings must be strings, arrays must be arrays
"""
    return dedent(prompt).strip()


def enhance_source_code(
    *,
    agent: Agent,
    sources: Sequence[Dict[str, str]],
    error_context: Optional[List[Dict[str, str]]] = None,
) -> List[EnhancedSource]:
    """
    Enhance source code snippets to be self-contained and executable.
    
    Args:
        agent: pydantic-ai Agent for LLM calls
        sources: List of source dicts with "file_path" and "code" keys
        error_context: Optional list of error dicts from previous execution attempts
        
    Returns:
        List of EnhancedSource objects with enhanced code
    """
    enhanced_sources = []
    
    for source in sources:
        file_path = source.get("file_path", "unknown.py")
        code = source.get("code", "")
        
        # Filter error context to this specific file if available
        file_errors = None
        if error_context:
            file_errors = [
                err for err in error_context 
                if err.get("file_path") == file_path
            ]
            # If no file-specific errors, use all errors as context
            if not file_errors:
                file_errors = error_context
        
        prompt = build_enhancement_prompt(code, file_path, file_errors)
        
        try:
            run_result = agent.run_sync(prompt, output_type=EnhancedSource)
            enhanced_sources.append(run_result.output)
        except Exception as e:
            # If enhancement fails, return original code with error note
            enhanced_sources.append(
                EnhancedSource(
                    file_path=file_path,
                    enhanced_code=code,  # Fallback to original
                    added_imports=[],
                    reasoning=f"Enhancement failed: {str(e)}. Using original code.",
                )
            )
    
    return enhanced_sources

