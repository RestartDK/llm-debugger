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
5. Return data that strictly matches the JSON schema:
   {{
     "target_function": "...",
     "summary": "...",
     "test_style": "pytest|unittest|doctest|custom",
     "tests": [
       {{
         "name": "...",
         "description": "...",
         "input": "...",
         "expected_output": "...",
         "notes": "..."
       }}
     ]
   }}

Rules:
- Prefer pytest-style parametrization when it reduces duplication.
- Avoid pseudo-code, return concrete Python snippets where relevant.
- Do not reference variables that were never defined (e.g., always define `result` before using it).
- If multiple helper functions are present, clarify which one each test targets.
"""
    return dedent(prompt).strip()


def generate_tests_for_code(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
) -> GeneratedTestSuite:
    """
    Call Gemini (through the provided pydantic-ai Agent) and return a structured
    test suite suggestion for the given code snippet.
    """

    prompt = build_test_gen_prompt(code_snippet, context)
    run_result = agent.run_sync(prompt, output_type=GeneratedTestSuite)
    return run_result.output


