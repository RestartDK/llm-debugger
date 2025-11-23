"""
Test case execution.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core.agent import LlmDebugAgent
from core.debug_types import BasicBlock
from core.dummy_cfg import get_dummy_blocks, get_dummy_sources
from core.llm_workflow_orchestrator import (
    build_debugger_ui_payload,
    run_generated_test_through_tracer_and_analyze,
)


class DebuggerPayload(TypedDict, total=False):
    suite: dict[str, Any]
    test_case: dict[str, Any]
    trace: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    problems: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    analysis: dict[str, Any]
    errors: list[dict[str, Any]]  # List of error objects with stack traces
    warnings: list[dict[str, Any]]  # List of warnings
    execution_log: list[dict[str, Any]]  # Structured log of execution steps
    source_loading_status: dict[str, Any]  # Status of each source file


def execute_test_cases(data: dict[str, Any]) -> DebuggerPayload:
    """
    Execute LLM-generated tests through the tracer and return debugger payload.

    Args:
        data: JSON body from POST /execute_test_cases. Supports:
            - task_description: human readable text for the debugging run.
            - sources: optional list of {"file_path", "code"} dicts.
            - blocks: optional list of {"block_id", "file_path", "start_line", "end_line"} dicts.
    """

    task_description = data.get(
        "task_description", "Investigate generated test failure"
    )

    sources = data.get("sources") or get_dummy_sources()
    
    # Convert blocks from dict format to BasicBlock objects if provided
    blocks_raw = data.get("blocks")
    if blocks_raw:
        blocks = [
            BasicBlock(
                block_id=block_dict.get("block_id", ""),
                file_path=block_dict.get("file_path", ""),
                start_line=block_dict.get("start_line", 0),
                end_line=block_dict.get("end_line", 0),
            )
            for block_dict in blocks_raw
            if block_dict.get("block_id") and block_dict.get("file_path")
        ]
        if not blocks:
            # If conversion failed, fall back to dummy blocks
            blocks = get_dummy_blocks()
    else:
        blocks = get_dummy_blocks()

    agent = LlmDebugAgent()
    run_result = run_generated_test_through_tracer_and_analyze(
        agent=agent,
        task_description=task_description,
        sources=sources,
        blocks=blocks,
    )
    payload: DebuggerPayload = build_debugger_ui_payload(run_result)  # type: ignore[assignment]

    required_fields = (
        "suite",
        "test_case",
        "trace",
        "steps",
        "problems",
        "nodes",
        "edges",
        "analysis",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"Debugger payload missing required fields: {', '.join(missing)}"
        )
    return payload


