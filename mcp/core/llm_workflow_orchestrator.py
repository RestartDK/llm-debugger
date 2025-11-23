from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .agent import LlmDebugAgent
from .debug_analysis_llm import (
    BlockInfo,
    DebugAnalysis,
    FailedTest,
    RuntimeStateSnapshot,
)
from .debug_types import BasicBlock
from .dummy_cfg import get_dummy_blocks, get_dummy_sources
from .mcp_tools import build_runner_payload, run_with_block_tracing_subprocess
from .test_generation_llm import GeneratedTestCase, GeneratedTestSuite


def render_generated_test_case_to_python(
    case: GeneratedTestCase, suite: GeneratedTestSuite
) -> str:
    """
    Render a GeneratedTestCase into runnable Python code.

    The prompt should ensure `case.input` contains the code that prepares inputs
    and calls the target under test, while `case.expected_output` contains the
    assertions that must hold.
    """

    header = dedent(
        f"""
        # LLM-generated test: {case.name}
        # Target scope: {suite.target_function}
        # Description: {case.description}
        """
    ).strip()

    return "\n\n".join(
        part.strip()
        for part in (header, case.input or "", case.expected_output or "")
        if part and part.strip()
    )


def _extract_code_snippet(
    source_lines: Sequence[str], start_line: int | None, end_line: int | None
) -> str:
    if not source_lines:
        return ""
    start_idx = max((start_line or 1) - 1, 0)
    end_idx = end_line or len(source_lines)
    end_idx = min(end_idx, len(source_lines))
    return "\n".join(source_lines[start_idx:end_idx])


def _build_block_info_lookup(
    blocks: Iterable[BasicBlock],
    sources: Sequence[Dict[str, str]],
) -> Dict[str, BlockInfo]:
    source_map: Dict[str, List[str]] = {
        entry["file_path"]: entry["code"].splitlines() for entry in sources
    }

    lookup: Dict[str, BlockInfo] = {}
    for block in blocks:
        lines = source_map.get(block.file_path, [])
        snippet = _extract_code_snippet(lines, block.start_line, block.end_line)
        lookup[block.block_id] = BlockInfo(
            id=block.block_id,
            code=snippet,
            file_path=block.file_path,
            start_line=block.start_line,
            end_line=block.end_line,
        )
    return lookup


def _build_runtime_snapshots_from_trace(
    trace_entries: Sequence[Dict[str, Any]],
) -> List[Tuple[str, RuntimeStateSnapshot]]:
    """
    Build RuntimeStateSnapshots for the first execution of each block in order.
    """

    ordered = sorted(trace_entries, key=lambda entry: entry.get("step_index", 0))
    snapshots: List[Tuple[str, RuntimeStateSnapshot]] = []
    seen_blocks: set[str] = set()
    previous_locals: Dict[str, Any] = {}

    for entry in ordered:
        block_id = entry.get("block_id")
        if not block_id or block_id in seen_blocks:
            previous_locals = entry.get("locals", previous_locals) or previous_locals
            continue

        before_locals = dict(previous_locals)
        after_locals = dict(entry.get("locals", {}))
        snapshots.append(
            (
                block_id,
                RuntimeStateSnapshot(
                    before=before_locals,
                    after=after_locals,
                    block_id=block_id,
                ),
            )
        )
        seen_blocks.add(block_id)
        previous_locals = after_locals

    return snapshots


@dataclass
class LlmDebugRunResult:
    suite: GeneratedTestSuite
    test_case: GeneratedTestCase
    trace_payload: Dict[str, Any]
    debug_analysis: DebugAnalysis


def run_generated_test_through_tracer_and_analyze(
    *,
    agent: LlmDebugAgent,
    task_description: str,
    sources: Sequence[Dict[str, str]] | None = None,
    blocks: Sequence[BasicBlock] | None = None,
    test_index: int = 0,
) -> LlmDebugRunResult:
    """
    End-to-end pipeline:
    1. Generate a suite of tests for the provided sources.
    2. Render a chosen test into executable Python.
    3. Run the test through the CFG tracer subprocess.
    4. Convert the trace into BlockInfo + RuntimeStateSnapshots.
    5. Ask the LLM to diagnose which blocks misbehaved.
    """

    source_entries = list(sources) if sources is not None else get_dummy_sources()
    if not source_entries:
        raise ValueError("No source files provided for test generation.")

    code_snippet = source_entries[0]["code"]
    suite = agent.generate_tests_for_code(code_snippet=code_snippet)

    if not suite.tests:
        raise ValueError("LLM did not return any generated tests.")
    if not (0 <= test_index < len(suite.tests)):
        raise IndexError(f"test_index {test_index} outside range of generated tests.")

    test_case = suite.tests[test_index]
    tests_code = render_generated_test_case_to_python(test_case, suite)

    block_entries = list(blocks) if blocks is not None else get_dummy_blocks()
    payload = build_runner_payload(
        sources=source_entries,
        blocks=block_entries,
        tests=tests_code,
    )
    trace_payload = run_with_block_tracing_subprocess(payload=payload)
    trace_entries: List[Dict[str, Any]] = trace_payload.get("trace", []) or []
    error_info: Dict[str, Any] | None = trace_payload.get("error")

    block_lookup = _build_block_info_lookup(block_entries, source_entries)
    snapshot_pairs = _build_runtime_snapshots_from_trace(trace_entries)

    block_infos: List[BlockInfo] = []
    runtime_states: List[RuntimeStateSnapshot] = []
    for block_id, snapshot in snapshot_pairs:
        block_info = block_lookup.get(block_id)
        if block_info is None:
            continue
        block_infos.append(block_info)
        runtime_states.append(snapshot)

    if not block_infos or not runtime_states:
        raise RuntimeError("Trace did not yield any executable blocks to analyze.")

    actual_description = (
        error_info.get("message", "All assertions passed (no error)")
        if error_info
        else "All assertions passed (no error)"
    )
    notes = error_info.get("traceback") if error_info else None

    failed_test = FailedTest(
        name=test_case.name,
        input=test_case.input,
        expected=test_case.expected_output,
        actual=actual_description,
        notes=notes,
    )

    debug_analysis = agent.analyze_failed_test(
        task_description=task_description,
        blocks=block_infos,
        runtime_states=runtime_states,
        failed_test=failed_test,
    )

    return LlmDebugRunResult(
        suite=suite,
        test_case=test_case,
        trace_payload=trace_payload,
        debug_analysis=debug_analysis,
    )


