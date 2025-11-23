from __future__ import annotations

import json
from typing import List, Sequence

from core.agent import LlmDebugAgent
from core.debug_analysis_llm import (
    BlockInfo,
    DebugAnalysis,
    FailedTest,
    RuntimeStateSnapshot,
)
from core.dummy_cfg import get_dummy_sources
from core.llm_workflow_orchestrator import (
    LlmDebugRunResult,
    run_generated_test_through_tracer_and_analyze,
)
from core.test_generation_llm import GeneratedTestSuite


def _default_block_scenarios() -> tuple[
    Sequence[BlockInfo], Sequence[RuntimeStateSnapshot]
]:
    """
    Provide a tiny hard-coded scenario that demonstrates the debugging flow.
    """

    blocks: List[BlockInfo] = [
        BlockInfo(
            id="calc:items_loop",
            code="""
subtotal = 0
for item in items:
    subtotal += item["price"] * item["quantity"]
""",
            file_path="demo/orders.py",
            start_line=1,
            end_line=4,
        ),
        BlockInfo(
            id="calc:apply_discount",
            code="""
if user_tier == "premium":
    subtotal *= 0.8
""",
            file_path="demo/orders.py",
            start_line=6,
            end_line=8,
        ),
    ]
    runtime_states: List[RuntimeStateSnapshot] = [
        RuntimeStateSnapshot(
            before={"items": [{"price": 10, "quantity": 2}]},
            after={"subtotal": 20},
            block_id="calc:items_loop",
        ),
        RuntimeStateSnapshot(
            before={"subtotal": 20, "user_tier": "standard"},
            after={"subtotal": 20},
            block_id="calc:apply_discount",
        ),
    ]
    return blocks, runtime_states


def demo_generate_tests_for_code(
    *,
    code_snippet: str | None = None,
    context: str | None = None,
    agent: LlmDebugAgent | None = None,
) -> GeneratedTestSuite:
    """
    Run the generic test generator using the provided code snippet (or a default).
    """

    agent = agent or LlmDebugAgent()
    if code_snippet is None:
        code_snippet = get_dummy_sources()[0]["code"]
    return agent.generate_tests_for_code(code_snippet=code_snippet, context=context)


def demo_analyze_failed_test(
    *,
    task_description: str = "Investigate discount logic regression",
    agent: LlmDebugAgent | None = None,
) -> DebugAnalysis:
    """
    Run the debug analysis flow using synthetic block/runtime data.
    """

    agent = agent or LlmDebugAgent()
    blocks, runtime_states = _default_block_scenarios()
    failed_test = FailedTest(
        name="test_premium_discount",
        input="items=[{'price': 10, 'quantity': 2}], user_tier='premium'",
        expected="final_total == 16",
        actual="final_total == 20",
        notes="Premium discount branch seems skipped.",
    )
    return agent.analyze_failed_test(
        task_description=task_description,
        blocks=blocks,
        runtime_states=runtime_states,
        failed_test=failed_test,
    )


def demo_full_llm_debug_from_generated_test(
    *,
    task_description: str = "Investigate e-commerce order processing bug",
    agent: LlmDebugAgent | None = None,
) -> LlmDebugRunResult:
    """
    Run the complete workflow: generate tests, trace execution, and analyze blocks.
    """

    agent = agent or LlmDebugAgent()
    return run_generated_test_through_tracer_and_analyze(
        agent=agent,
        task_description=task_description,
    )


if __name__ == "__main__":
    demo_agent = LlmDebugAgent()
    suite = demo_generate_tests_for_code(agent=demo_agent)
    analysis = demo_analyze_failed_test(agent=demo_agent)
    full_run = demo_full_llm_debug_from_generated_test(agent=demo_agent)
    print("=== Generated Test Suite ===")
    print(suite.model_dump_json(indent=2))
    print("\n=== Debug Analysis ===")
    print(analysis.model_dump_json(indent=2))
    print("\n=== Full LLM Debug Run ===")
    print("Chosen Test Case:")
    print(full_run.test_case.model_dump_json(indent=2))
    print("\nTrace Payload:")
    print(json.dumps(full_run.trace_payload, indent=2))
    print("\nLLM Block Analysis:")
    print(full_run.debug_analysis.model_dump_json(indent=2))

