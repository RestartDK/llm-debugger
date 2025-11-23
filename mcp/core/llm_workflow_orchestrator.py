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
from textwrap import dedent as _dedent
import asyncio
from . import mcp_routes


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
    blocks: List[BlockInfo]
    runtime_states: List[RuntimeStateSnapshot]

def apply_suggested_fixes_to_source(
    
    agent: LlmDebugAgent,
    task_description: str,
    instructions: str,
) -> None:
    """
    Apply suggested fixes to repository source files.

    The function expects `instructions` to contain one or more "[Code Chunk]"
    sections with a `File: <path>` line, a `Changed:` block and a `To:` block
    describing the replacement. Example (see `core.dummy_cfg.get_dummy_fix_instructions`):

        [Code Chunk]
        File: mcp/main.py

        Changed:
        <original snippet>

        To:
        <replacement snippet>

    This implementation is intentionally conservative:
    - Only files explicitly listed by `File:` are modified.
    - The first exact occurrence of the `Changed:` snippet is replaced.
    - A timestamped backup is written beside the original before modifying it.
    - If the `Changed:` snippet can't be found, the function skips that chunk and logs a message.

    Args:
        agent: LlmDebugAgent (not used directly here but retained for call-site compatibility).
        task_description: Human-readable task description (unused here).
        instructions: The raw instructions text returned by the LLM containing patches.

    Returns:
        None
    """

    if not instructions:
        raise ValueError("No instructions provided to apply_suggested_fixes_to_source")

    # Normalize the instructions text and forward to MCP as a tool call.
    text = _dedent(task_description).strip() + _dedent(instructions).strip()

    # Build a tools/call request to invoke the MCP tool that handles code context
    params = {
        "name": "submit_code_context_mcp",
        "arguments": {"text": text},
    }

    # Attempt to schedule the MCP request on the running event loop so that
    # the MCP machinery can route the response (and potentially forward to Cursor).
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    async def _invoke():
        try:
            # process_mcp_request will return a JSON-RPC response dict
            response = await mcp_routes.process_mcp_request(
                method="tools/call",
                params=params,
                request_id=None,
                mcp_instance=None,
                connection_id=None,
            )
            # print("MCP forwarded suggestions, response:", response)
            return response
        except Exception as e:
            # print("Error forwarding suggestions to MCP:", e)
            return {"error": str(e)}

    if loop:
        # Schedule asynchronously and don't block the caller
        loop.create_task(_invoke())
    else:
        # No running loop — run synchronously
        try:
            result = asyncio.run(_invoke())
            print("MCP forwarded suggestions (sync), response:", result)
        except Exception as e:
            print("Failed to forward suggestions to MCP:", e)

    return

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
    print(
        "[orchestrator] runner payload summary:",
        {
            "sources": [entry["file_path"] for entry in source_entries],
            "blocks": [block.block_id for block in block_entries],
            "tests_code_preview": tests_code[:200],
        },
    )
    trace_payload = run_with_block_tracing_subprocess(payload=payload)
    trace_entries: List[Dict[str, Any]] = trace_payload.get("trace", []) or []
    error_info: Dict[str, Any] | None = trace_payload.get("error")
    stderr_text = trace_payload.get("stderr")
    print(
        f"[orchestrator] trace_entries count: {len(trace_entries)}, "
        f"error_info: {error_info}",
    )
    if stderr_text:
        print("[orchestrator] runner stderr:\n", stderr_text)

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
        # Provide rich diagnostics so it's easier to understand why nothing
        # was analyzable (no trace at all vs. trace that didn't match blocks).
        trace_block_ids = [
            entry.get("block_id")
            for entry in trace_entries
            if entry.get("block_id") is not None
        ]
        print(
            "[orchestrator] no executable blocks found; debug summary:",
            {
                "trace_entry_count": len(trace_entries),
                "trace_block_ids_sample": trace_block_ids[:10],
                "snapshot_pairs_count": len(snapshot_pairs),
                "block_lookup_ids_sample": list(block_lookup.keys())[:10],
            },
        )
        
        # Test failed before executing any blocks (e.g., syntax error, missing function call)
        # Return a minimal result with error information but no block analysis
        actual_description = (
            error_info.get("message", "Test failed before executing any code blocks")
            if error_info
            else "Test failed before executing any code blocks"
        )
        notes = error_info.get("traceback") if error_info else None
        
        # Create a minimal debug analysis indicating no blocks were executed
        from .debug_analysis_llm import DebugAnalysis
        failed_test = FailedTest(
            name=test_case.name,
            input=test_case.input,
            expected=test_case.expected_output,
            actual=actual_description,
            notes=notes,
        )
        debug_analysis = DebugAnalysis(
            task_description=(
                f"Test '{test_case.name}' failed before executing any code blocks. "
                f"Error: {actual_description}. "
                f"The test may be missing a function call or has a syntax error. "
                f"Check that the test input includes the actual function invocation."
            ),
            failed_test=failed_test,
            assessments=[],  # No blocks to assess since none were executed
        )
        
        return LlmDebugRunResult(
            suite=suite,
            test_case=test_case,
            trace_payload=trace_payload,
            debug_analysis=debug_analysis,
            blocks=[],
            runtime_states=[],
        )

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
        blocks=block_infos,
        runtime_states=runtime_states,
    )


def build_debugger_ui_payload(run_result: LlmDebugRunResult) -> Dict[str, object]:
    """
    Convert an LlmDebugRunResult into a Branch/frontend friendly payload.
    """

    trace_entries: List[Dict[str, Any]] = (
        run_result.trace_payload.get("trace", []) or []
    )
    block_lookup: Dict[str, BlockInfo] = {block.id: block for block in run_result.blocks}

    # Build RuntimeStep-like structures from trace entries
    steps: List[Dict[str, Any]] = []
    previous_locals: Dict[str, Any] = {}
    ordered_trace = sorted(trace_entries, key=lambda entry: entry.get("step_index", 0))
    for entry in ordered_trace:
        block_id = entry.get("block_id")
        if not block_id:
            continue
        block = block_lookup.get(block_id)
        step_index = entry.get("step_index", 0)
        current_locals = entry.get("locals", {}) or {}
        step = {
            "id": f"{block_id}-step-{step_index}",
            "blockId": block_id,
            "blockName": block_id,
            "codeSnippet": block.code if block else "",
            "before": dict(previous_locals),
            "after": dict(current_locals),
            "status": "succeeded",
        }
        steps.append(step)
        previous_locals = current_locals

    # Identify incorrect blocks from LLM analysis to build problems + mark failures
    incorrect_blocks: Dict[str, str] = {}
    for assessment in run_result.debug_analysis.assessments:
        if assessment.correct:
            continue
        label = assessment.block
        try:
            idx = int(label.split("-")[-1])
        except ValueError:
            continue
        if 0 <= idx < len(run_result.blocks):
            block_id = run_result.blocks[idx].id
            incorrect_blocks[block_id] = assessment.explanation

    problems: List[Dict[str, Any]] = []
    for idx, (block_id, explanation) in enumerate(incorrect_blocks.items()):
        step = next((candidate for candidate in steps if candidate["blockId"] == block_id), None)
        problems.append(
            {
                "id": f"prob-{idx}",
                "blockId": block_id,
                "stepId": step["id"] if step else "",
                "description": explanation,
                "severity": "error",
            }
        )
        if step:
            step["status"] = "failed"
            step["error"] = explanation

    # Build CFG nodes (basic placeholders) and attach execution counts
    execution_counts: Dict[str, int] = {}
    for step in steps:
        execution_counts[step["blockId"]] = execution_counts.get(step["blockId"], 0) + 1

    nodes: List[Dict[str, Any]] = []
    for block in run_result.blocks:
        block_id = block.id
        nodes.append(
            {
                "id": block_id,
                "type": "cfgNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "blockId": block_id,
                    "blockName": block_id,
                    "codeSnippet": block.code,
                    "status": "failed" if block_id in incorrect_blocks else "succeeded",
                    "file": block.file_path,
                    "lineStart": block.start_line,
                    "lineEnd": block.end_line,
                    "executionCount": execution_counts.get(block_id, 0),
                },
            }
        )

    # Build simple sequential edges per file (placeholder CFG)
    edges: List[Dict[str, Any]] = []
    prev_block_for_file: Dict[str, str] = {}
    sorted_blocks = sorted(
        run_result.blocks,
        key=lambda block: ((block.file_path or ""), block.start_line or 0),
    )
    for block in sorted_blocks:
        file_path = block.file_path or ""
        prev_block = prev_block_for_file.get(file_path)
        if prev_block:
            edges.append(
                {
                    "id": f"edge-{prev_block}-{block.id}",
                    "source": prev_block,
                    "target": block.id,
                }
            )
        prev_block_for_file[file_path] = block.id

    return {
        "suite": run_result.suite.model_dump(),
        "test_case": run_result.test_case.model_dump(),
        "trace": trace_entries,
        "steps": steps,
        "problems": problems,
        "nodes": nodes,
        "edges": edges,
        "analysis": run_result.debug_analysis.model_dump(),
    }


