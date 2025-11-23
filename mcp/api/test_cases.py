"""
Test case execution.
"""

from core.agent import LlmDebugAgent
from core.dummy_cfg import get_dummy_blocks, get_dummy_sources
from core.llm_workflow_orchestrator import (
    build_debugger_ui_payload,
    run_generated_test_through_tracer_and_analyze,
)


def execute_test_cases(data: dict) -> dict:
    """
    Execute LLM-generated tests through the tracer and return debugger payload.
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
    return build_debugger_ui_payload(run_result)


