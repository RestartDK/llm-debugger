"""
Test case execution.
"""

from __future__ import annotations

import sys
from typing import Any, TypedDict

from core.agent import LlmDebugAgent
from core.debug_types import BasicBlock
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
            - blocks: optional list of {"block_id", "file_path", "start_line", "end_line"} dicts.
    """
    print("[test_cases] ===== Starting test case execution workflow =====", file=sys.stderr)
    print(
        f"[test_cases] Received request data: task_description={'present' if data.get('task_description') else 'missing'}, "
        f"sources_count={len(data.get('sources', []))}, "
        f"blocks_count={len(data.get('blocks', []))}",
        file=sys.stderr,
    )

    task_description = data.get(
        "task_description", "Investigate generated test failure"
    )
    print(f"[test_cases] Task description: {task_description[:100]}...", file=sys.stderr)

    sources = data.get("sources")
    if not sources:
        print("[test_cases] WARNING: No sources provided in request, using DUMMY sources", file=sys.stderr)
        sources = get_dummy_sources()
    else:
        print(f"[test_cases] Using {len(sources)} provided source file(s)", file=sys.stderr)
    
    # Convert blocks from dict format to BasicBlock objects if provided
    blocks_raw = data.get("blocks")
    if blocks_raw:
        print(f"[test_cases] Converting {len(blocks_raw)} blocks from dict format...", file=sys.stderr)
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
            print("[test_cases] WARNING: Block conversion failed, using dummy blocks", file=sys.stderr)
            blocks = get_dummy_blocks()
        else:
            print(f"[test_cases] Successfully converted {len(blocks)} blocks", file=sys.stderr)
    else:
        print("[test_cases] No blocks provided, using dummy blocks", file=sys.stderr)
        blocks = get_dummy_blocks()

    print("[test_cases] Initializing LlmDebugAgent...", file=sys.stderr)
    agent = LlmDebugAgent()
    print("[test_cases] Calling run_generated_test_through_tracer_and_analyze...", file=sys.stderr)
    run_result = run_generated_test_through_tracer_and_analyze(
        agent=agent,
        task_description=task_description,
        sources=sources,
        blocks=blocks,
    )
    print("[test_cases] Building debugger UI payload...", file=sys.stderr)
    payload: DebuggerPayload = build_debugger_ui_payload(run_result)  # type: ignore[assignment]
    print(
        f"[test_cases] Payload built: trace_entries={len(payload.get('trace', []))}, "
        f"steps={len(payload.get('steps', []))}, problems={len(payload.get('problems', []))}",
        file=sys.stderr,
    )
    print("[test_cases] ===== Test case execution workflow completed =====", file=sys.stderr)

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


