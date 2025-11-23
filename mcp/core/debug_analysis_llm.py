from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class FailedTest(BaseModel):
    """
    Description of the failing scenario we are trying to debug.
    """

    name: Optional[str] = Field(default=None, description="Identifier for the test")
    input: str = Field(..., description="Serialized representation of the test input")
    expected: str = Field(..., description="What the program should have produced")
    actual: str = Field(..., description="What the program actually produced")
    notes: Optional[str] = Field(default=None, description="Any extra context")


class RuntimeStateSnapshot(BaseModel):
    """
    Captured locals immediately before and after executing a block.
    """

    before: Dict[str, object] = Field(
        default_factory=dict,
        description="Locals/vars before entering the block",
    )
    after: Dict[str, object] = Field(
        default_factory=dict,
        description="Locals/vars after exiting the block",
    )
    block_id: Optional[str] = Field(
        default=None, description="Optional block identifier for convenience"
    )


class BlockInfo(BaseModel):
    """
    Static metadata for a CFG block used when formatting debug prompts.
    """

    id: str
    code: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class BlockAssessment(BaseModel):
    """
    Gemini's judgement per block (correct/incorrect + explanation).
    """

    block: str
    correct: bool
    explanation: str


class DebugAnalysis(BaseModel):
    """
    Response schema for the debugging prompt.
    """

    task_description: str
    failed_test: FailedTest
    assessments: List[BlockAssessment]


def _format_vars(values: Dict[str, object]) -> str:
    """
    Render locals dicts into a compact `name=value` list for the prompt.
    """

    if not values:
        return "∅"
    parts = []
    for key in sorted(values):
        parts.append(f"{key}={values[key]!r}")
    return ", ".join(parts)


def build_debug_prompt(
    *,
    task_description: str,
    blocks: Sequence[BlockInfo],
    runtime_states: Sequence[RuntimeStateSnapshot],
    failed_test: FailedTest,
) -> str:
    """
    Build the debugging prompt described in the spec.
    """

    if len(blocks) != len(runtime_states):
        raise ValueError(
            "blocks and runtime_states must be the same length "
            f"(got {len(blocks)} vs {len(runtime_states)})"
        )

    lines: List[str] = [
        "You are a precise Python debugger.",
        "",
        "The code fails this test:",
        f"Name: {failed_test.name or 'unnamed'}",
        f"Input: {failed_test.input}",
        f"Expected: {failed_test.expected}",
        f"Actual: {failed_test.actual}",
    ]
    if failed_test.notes:
        lines.append(f"Notes: {failed_test.notes}")

    lines.extend(
        [
            "",
            f"Task Description: {task_description}",
            "",
            "Here is the execution trace. For EACH block, say if it's correct or not.",
            "Use the provided task/test values verbatim when populating output JSON.",
        ]
    )

    for idx, (block, state) in enumerate(zip(blocks, runtime_states)):
        block_header = f"[BLOCK-{idx}] {block.id}"
        if block.file_path:
            block_header += f" ({block.file_path}:{block.start_line}-{block.end_line})"
        lines.extend(
            [
                "",
                block_header,
                f"# Before: {_format_vars(state.before)}",
                block.code.strip(),
                f"# After: {_format_vars(state.after)}",
            ]
        )

    lines.extend(
        [
            "",
            "CRITICAL: You MUST provide structured output matching this exact JSON schema:",
            "{",
            '  "task_description": "string (required - repeat the task description in your own words)",',
            '  "failed_test": {',
            '    "name": "string or null (optional)",',
            '    "input": "string (required)",',
            '    "expected": "string (required)",',
            '    "actual": "string (required)",',
            '    "notes": "string or null (optional)"',
            "  },",
            '  "assessments": [',
            '    { "block": "string (required - e.g., BLOCK-0)", "correct": "boolean (required - true/false)", "explanation": "string (required)" }',
            "  ]",
            "}",
            "",
            "IMPORTANT STRUCTURED OUTPUT RULES:",
            "- ALL required fields must be present and non-null",
            "- String fields must be actual strings, never null (unless explicitly marked as optional)",
            "- Boolean fields must be true or false, not strings",
            "- Arrays must be arrays with the correct structure",
            "- Match the schema types exactly",
            "- Do not include any narration outside of this JSON object.",
        ]
    )

    return "\n".join(lines).strip()


def analyze_failed_test(
    *,
    agent: Agent,
    task_description: str,
    blocks: Sequence[BlockInfo],
    runtime_states: Sequence[RuntimeStateSnapshot],
    failed_test: FailedTest,
) -> DebugAnalysis:
    """
    Send the debugging prompt to Gemini and parse the structured response.
    """

    prompt = build_debug_prompt(
        task_description=task_description,
        blocks=blocks,
        runtime_states=runtime_states,
        failed_test=failed_test,
    )
    run_result = agent.run_sync(prompt, output_type=DebugAnalysis)
    return run_result.output
