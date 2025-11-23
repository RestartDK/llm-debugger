from __future__ import annotations

import inspect
import re
import sys
import traceback
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


def _extract_target_function_from_code(code_snippet: str) -> Optional[str]:
    """
    Simple heuristic to identify main function/class being tested.
    Returns function name or None if unclear.
    """
    # Look for function definitions
    pattern = r'def\s+(\w+)\s*\('
    matches = re.findall(pattern, code_snippet)
    if matches:
        # Return first function found (usually the main one)
        return matches[0]
    return None


def build_test_code_prompt(code_snippet: str, context: Optional[str] = None) -> str:
    """
    Build a prompt for generating raw test code (unstructured output).
    Focuses on generating standalone, executable Python code blocks (NOT unittest classes).
    """
    extra_context = f"\nAdditional context:\n{context.strip()}" if context else ""

    prompt = f"""
You are a senior Python engineer creating simple tests for the following code.

Code under test:
```python
{code_snippet.strip()}
```
{extra_context}

Your task: Generate standalone, executable Python test code as simple code blocks.

CRITICAL REQUIREMENTS:
1. NO classes, NO `self`, NO unittest framework - just standalone Python code blocks
2. Each test should be a simple code block that can run independently
3. Generate 3-7 simple test cases covering:
   - Normal flow scenarios
   - Edge cases (empty inputs, boundary values)
   - Error paths (invalid inputs, exception handling)
4. Each test block MUST:
   - Set up any necessary mocks/stubs before calling the function
   - Call the target function and assign to `result` (e.g., `result = my_func(...)`)
   - Use simple `assert` statements (e.g., `assert result == expected_value`)
   - You can add random logic before and after the code being tested to make tests work
5. Tests must be STANDALONE and self-contained:
   - Mock ALL external dependencies (imports, globals, classes) within each test block
   - Do NOT assume any imports exist unless standard library
   - Create stub classes/functions inline if needed
   - "Bring your own mocks": If the code uses `requests.get`, mock it. If it uses `MyClass`, define a stub `MyClass` in the test block
6. Separate each test with clear comments like `# Test 1: normal case` or `# Test 2: edge case`
7. Keep tests SIMPLE - just verify "will this run" - no fancy logic needed

Format your response as Python code only. Do not include any explanation or metadata - just the test code.

Example structure:
```python
# Test 1: normal case
# Mock any dependencies here
result = my_function("input")
assert result == "expected"

# Test 2: edge case
result = my_function("")
assert result is not None

# Test 3: error case
try:
    result = my_function(None)
    assert False, "Should have raised error"
except ValueError:
    pass
```

Now generate the simple standalone test code:
"""
    return dedent(prompt).strip()


def generate_test_code_only(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
) -> str:
    """
    Step 1: Generate raw test code without structured output requirements.
    Returns raw Python test code string.
    """
    prompt = build_test_code_prompt(code_snippet, context)
    try:
        # Log Groq call location for debugging tool_use_failed errors
        stack = inspect.stack()
        caller_frame = stack[0]  # Current frame (this logging line)
        # Get the actual line number where run_sync is called (next line)
        call_line = caller_frame.lineno + 1
        caller_info = f"File: {__file__}, Line: {call_line}, Function: {caller_frame.function}, Output Type: unstructured (text only)"
        print(f"[groq_call] {caller_info}", file=sys.stderr)
        run_result = agent.run_sync(prompt)  # No output_type - just text generation
        test_code = run_result.output
        
        # Log the generated test code
        print(f"[test_gen] Step 1 - Generated test code:\n{test_code}", file=sys.stderr)
        
        return test_code
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[groq_error] Function: generate_test_code_only, Error Type: {error_type}, Message: {error_msg}", file=sys.stderr)
        if hasattr(e, 'status_code'):
            print(f"[groq_error] HTTP Status: {e.status_code}", file=sys.stderr)
        if hasattr(e, 'response'):
            print(f"[groq_error] Response: {e.response}", file=sys.stderr)
        print(f"[groq_error] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        raise  # Re-raise after logging


def build_metadata_extraction_prompt(
    generated_test_code: str,
    original_code_snippet: str,
    target_function: Optional[str] = None,
) -> str:
    """
    Build a prompt for extracting structured metadata from generated test code.
    Tests are standalone Python code blocks, not class methods.
    """
    if target_function is None:
        target_function = _extract_target_function_from_code(original_code_snippet) or "unknown"
    
    prompt = f"""
You are analyzing generated test code to extract structured metadata.

Original code being tested:
```python
{original_code_snippet.strip()}
```

Generated test code:
```python
{generated_test_code.strip()}
```

Target function: {target_function}

Your task: Analyze the generated test code and extract structured metadata for each test block.

The test code consists of standalone Python code blocks (NOT class methods). Each test block is separated by comments or blank lines.

For each test block, extract:
1. **name**: A descriptive name based on the test comment or logic (e.g., "normal_case", "edge_case_empty_input")
2. **description**: What behavior or edge case this test covers (infer from test logic/comments)
3. **input**: The test setup code and function call (the code that prepares inputs and calls the target function, including any mocks/stubs)
4. **expected_output**: The assertions or expected results (MUST be a string, never null. Extract all assert statements or expected values. If no assertions found, use empty string "")
5. **notes**: Any special setup, mocks, or fixtures used (optional)

CRITICAL: You MUST provide structured output matching this exact JSON schema:
{{
  "target_function": "string (required - the function being tested)",
  "summary": "string (required - high-level coverage summary)",
  "test_style": "standalone|custom (required - use 'standalone' since these are not unittest/pytest)",
  "tests": [
    {{
      "name": "string (required - descriptive test name)",
      "description": "string (required - what the test verifies)",
      "input": "string (required - setup code and function call)",
      "expected_output": "string (REQUIRED - must be a string, never null. Extract assertions or expected results. Use empty string '' if no assertions found)",
      "notes": "string or null (optional - special setup/mocks)"
    }}
  ]
}}

IMPORTANT STRUCTURED OUTPUT RULES:
- ALL required fields must be present and non-null
- The "expected_output" field MUST ALWAYS be a string. If there are no assertions, use an empty string "" instead of null
- The "expected_output" field should contain the actual assertion statements or expected results as a string (e.g., "assert result == 5" or "assert result is None")
- Ensure all string fields are actual strings, not null values
- Match the schema types exactly: strings must be strings, lists must be lists, etc.
- Extract the "input" field as the code that sets up the test (including mocks) and calls the target function
- Extract the "expected_output" field as the assertion statements or expected results from the test
- The test code does NOT use classes or `self` - it's standalone Python code blocks

Analyze the test code and provide the structured output:
"""
    return dedent(prompt).strip()


def extract_test_metadata(
    *,
    agent: Agent,
    generated_test_code: str,
    original_code_snippet: str,
    target_function: Optional[str] = None,
) -> GeneratedTestSuite:
    """
    Step 2: Extract structured metadata from generated test code.
    Returns GeneratedTestSuite Pydantic model.
    """
    prompt = build_metadata_extraction_prompt(
        generated_test_code, original_code_snippet, target_function
    )
    try:
        # Log Groq call location for debugging tool_use_failed errors
        stack = inspect.stack()
        caller_frame = stack[0]  # Current frame (this logging line)
        # Get the actual line number where run_sync is called (next line)
        call_line = caller_frame.lineno + 1
        caller_info = f"File: {__file__}, Line: {call_line}, Function: {caller_frame.function}, Output Type: structured (GeneratedTestSuite)"
        print(f"[groq_call] {caller_info}", file=sys.stderr)
        run_result = agent.run_sync(prompt, output_type=GeneratedTestSuite)
        suite = run_result.output
        
        # Log the extracted metadata
        print(f"[test_gen] Step 2 - Extracted metadata:\n{suite.model_dump_json(indent=2)}", file=sys.stderr)
        
        return suite
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[groq_error] Function: extract_test_metadata, Error Type: {error_type}, Message: {error_msg}", file=sys.stderr)
        if hasattr(e, 'status_code'):
            print(f"[groq_error] HTTP Status: {e.status_code}", file=sys.stderr)
        if hasattr(e, 'response'):
            print(f"[groq_error] Response: {e.response}", file=sys.stderr)
        print(f"[groq_error] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        raise  # Re-raise after logging


def build_test_gen_prompt(code_snippet: str, context: Optional[str] = None) -> str:
    """
    Build a domain-agnostic prompt that asks Gemini to invent useful tests.
    """

    extra_context = f"\nAdditional context:\n{context.strip()}" if context else ""

    prompt = f"""
You are a senior Python engineer creating tests for the following code.

Code under test:
```python
{code_snippet.strip()}
```
{extra_context}

Goals:
1. Infer realistic inputs and outputs directly from the code (no domain assumptions).
2. Cover normal flow plus edge cases (empty inputs, error paths, boundary values).
3. Produce deterministic tests with explicit assertions.
4. Each test case MUST invoke the target function explicitly, assign the call to a variable named `result` (e.g., `result = my_func(...)`), and assert on `result` (or its fields) right after.
5. Tests must be STANDALONE. Mock ALL external dependencies (imports, globals, classes) in the test input itself. Do NOT assume any imports exist unless standard library.
6. Create MULTIPLE GRANULAR tests covering specific functionality.
7. Provide structured output that strictly matches the JSON schema below. ALL fields must be present and of the correct type.

CRITICAL: You MUST provide structured output matching this exact schema:
{{
  "target_function": "string (required)",
  "summary": "string (required)",
  "test_style": "pytest|unittest|doctest|custom (required)",
  "tests": [
    {{
      "name": "string (required)",
      "description": "string (required)",
      "input": "string (required)",
      "expected_output": "string (REQUIRED - must be a string, never null. Use empty string '' if no output expected, but always provide a string)",
      "notes": "string or null (optional)"
    }}
  ]
}}

IMPORTANT STRUCTURED OUTPUT RULES:
- ALL required fields must be present and non-null
- The "expected_output" field MUST ALWAYS be a string. If there is no expected output, use an empty string "" instead of null
- The "expected_output" field should contain assertions or expected results as a string (e.g., "assert result == 5" or "assert result is None")
- Ensure all string fields are actual strings, not null values
- Match the schema types exactly: strings must be strings, lists must be lists, etc.

Rules:
- Prefer pytest-style parametrization when it reduces duplication.
- Avoid pseudo-code, return concrete Python snippets where relevant.
- Do not reference variables that were never defined.
- If multiple helper functions are present, clarify which one each test targets.
- Use `unittest.mock` or create stub classes/functions for any missing dependencies.
- "Bring your own mocks": If the code uses `requests.get`, mock it. If it uses `MyClass`, define a stub `MyClass` in the input code.
"""
    return dedent(prompt).strip()


def generate_tests_for_code(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
) -> GeneratedTestSuite:
    """
    Main entry point: Generate tests using two-step approach.
    Step 1: Generate raw test code
    Step 2: Extract structured metadata
    
    Returns GeneratedTestSuite Pydantic model.
    """
    # Step 1: Generate test code
    test_code = generate_test_code_only(
        agent=agent, code_snippet=code_snippet, context=context
    )
    
    # Step 2: Extract metadata
    suite = extract_test_metadata(
        agent=agent,
        generated_test_code=test_code,
        original_code_snippet=code_snippet,
    )
    
    return suite


