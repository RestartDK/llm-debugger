from __future__ import annotations

from textwrap import dedent
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class GeneratedTestCase(BaseModel):
    """
    Structured representation of a single generated test scenario.
    """

    name: str = Field(..., description="Human-readable name for the test")
    description: str = Field(..., description="What behavior or edge case it covers")
    input: str = Field(..., description="Python code or dict describing test inputs")
    expected_output: str = Field(..., description="Expected outcome / assertions")
    notes: Optional[str] = Field(
        default=None, description="Any extra hints (fixtures, cleanup, etc.)"
    )
    mock_setup: Optional[str] = Field(
        default=None, description="Code to set up mocks/stubs for external dependencies"
    )
    dependencies: Optional[List[str]] = Field(
        default=None, description="List of dependencies that need mocking"
    )


class GeneratedTestSuite(BaseModel):
    """
    Collection of test cases plus metadata for the target under test.
    """

    target_function: str = Field(
        ..., description="Function/module/class the tests are written for"
    )
    summary: str = Field(..., description="High-level coverage summary")
    test_style: str = Field(
        default="pytest",
        description="Suggested testing style (pytest, unittest, doctest, etc.)",
    )
    tests: List[GeneratedTestCase] = Field(
        default_factory=list, description="Concrete test cases"
    )


def build_test_gen_prompt(code_snippet: str, context: Optional[str] = None, target_function: Optional[str] = None) -> str:
    """
    Build a domain-agnostic prompt that asks Gemini to invent useful tests.
    Emphasizes isolation, mocking, and minimal dependencies.
    """

    extra_context = f"\nAdditional context:\n{context.strip()}" if context else ""
    function_context = f"\nTarget function to test: {target_function}" if target_function else ""

    prompt = f"""
You are a senior Python engineer creating ISOLATED, MOCKED tests for the following code.

Code under test:
```python
{code_snippet.strip()}
```
{function_context}{extra_context}

CRITICAL REQUIREMENTS FOR ISOLATION:
1. **Mock ALL external dependencies**: Import statements, classes, functions, enums, constants from other modules MUST be mocked.
2. **Use unittest.mock or MagicMock**: Create mock objects for any external dependencies.
3. **Test individual functions**: Focus on testing the specific function, not entire modules.
4. **Minimal dependencies**: Use only Python standard library + mocks. No file system, network, or complex imports.
5. **Self-contained tests**: Tests must run without external files, databases, or services.

Goals:
1. Infer realistic inputs and outputs directly from the code (no domain assumptions).
2. Cover normal flow plus edge cases (empty inputs, error paths, boundary values).
3. Produce deterministic tests with explicit assertions.
4. Each test case MUST:
   - Set up mocks for all external dependencies in `mock_setup` field
   - Invoke the target function explicitly, assign the call to a variable named `result` (e.g., `result = my_func(...)`)
   - Assert on `result` (or its fields) right after
5. Return data that strictly matches the JSON schema:
   {{
     "target_function": "...",
     "summary": "...",
     "test_style": "pytest|unittest|doctest|custom",
     "tests": [
       {{
         "name": "...",
         "description": "...",
         "mock_setup": "from unittest.mock import MagicMock, patch\\n# Mock setup code here",
         "dependencies": ["module.Class", "module.function"],
         "input": "...",
         "expected_output": "...",
         "notes": "..."
       }}
     ]
   }}

Example of proper mock setup:
```python
from unittest.mock import MagicMock, patch

# Mock external dependencies
mock_dependency = MagicMock()
mock_dependency.method.return_value = "expected_value"

with patch("module.ExternalClass", return_value=mock_dependency):
    result = target_function(arg1, arg2)
    assert result == expected_value
```

Rules:
- ALWAYS include `mock_setup` code that mocks external dependencies
- List all dependencies that need mocking in `dependencies` field
- Prefer pytest-style parametrization when it reduces duplication
- Avoid pseudo-code, return concrete Python snippets where relevant
- Do not reference variables that were never defined (e.g., always define `result` before using it)
- If multiple helper functions are present, clarify which one each test targets
- Mock enums, constants, and classes from external modules
- Use MagicMock for complex objects that can't be easily instantiated
"""
    return dedent(prompt).strip()


def generate_tests_for_code(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
    target_function: Optional[str] = None,
) -> GeneratedTestSuite:
    """
    Call Gemini (through the provided pydantic-ai Agent) and return a structured
    test suite suggestion for the given code snippet.
    """
    import sys
    import time
    
    start_time = time.time()
    print(f"[test_gen] Starting test generation for function: {target_function or 'unknown'}", file=sys.stderr)
    print(f"[test_gen] Code snippet length: {len(code_snippet)} chars", file=sys.stderr)
    
    try:
        prompt = build_test_gen_prompt(code_snippet, context, target_function)
        print(f"[test_gen] Prompt built, calling LLM...", file=sys.stderr)
        
        run_result = agent.run_sync(prompt, output_type=GeneratedTestSuite)
        
        elapsed = time.time() - start_time
        print(f"[test_gen] Test generation completed in {elapsed:.2f}s", file=sys.stderr)
        print(f"[test_gen] Generated {len(run_result.output.tests)} test case(s)", file=sys.stderr)
        
        return run_result.output
    except Exception as e:
        import traceback
        elapsed = time.time() - start_time
        tb = traceback.format_exc()
        print(f"[test_gen] ERROR: Test generation failed after {elapsed:.2f}s", file=sys.stderr)
        print(f"[test_gen] Error: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"[test_gen] Traceback:\n{tb}", file=sys.stderr)
        raise


