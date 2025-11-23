"""
Test case execution.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core.agent import LlmDebugAgent
from core.dummy_cfg import get_dummy_blocks, get_dummy_sources
from core.llm_workflow_orchestrator import (
    build_debugger_ui_payload,
    run_generated_test_through_tracer_and_analyze,
)


class DebuggerPayload(TypedDict):
    suite: dict[str, Any]
    test_case: dict[str, Any]
    trace: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    problems: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    analysis: dict[str, Any]


def execute_test_cases(data: dict[str, Any]) -> DebuggerPayload:
    """
    Execute LLM-generated tests through the tracer and return debugger payload.

    Args:
        data: JSON body from POST /execute_test_cases. Supports:
            - task_description: human readable text for the debugging run.
            - sources: optional list of {"file_path", "code"} dicts.
    """

    task_description = data.get(
        "task_description", "Investigate generated test failure"
    )

    sources = data.get("sources") or get_dummy_sources()
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


