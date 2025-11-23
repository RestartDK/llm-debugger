"""
Control flow diagram generation.
"""

from core.agent import LlmDebugAgent
from core.dummy_cfg import get_dummy_blocks, get_dummy_sources
from core.llm_workflow_orchestrator import (
    build_debugger_ui_payload,
    run_generated_test_through_tracer_and_analyze,
)


def get_control_flow_diagram() -> dict:
    """
    Return nodes/edges describing the CFG derived from the dummy ecommerce flow.
    """

    agent = LlmDebugAgent()
    sources = get_dummy_sources()
    blocks = get_dummy_blocks()

    run_result = run_generated_test_through_tracer_and_analyze(
        agent=agent,
        task_description="Inspect control flow for dummy ecommerce pipeline",
        sources=sources,
        blocks=blocks,
    )
    payload = build_debugger_ui_payload(run_result)
    return {"nodes": payload["nodes"], "edges": payload["edges"]}

