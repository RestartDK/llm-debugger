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
import os
import re
from pathlib import Path
from datetime import datetime
from textwrap import dedent as _dedent


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
        print("No instructions provided to apply_suggested_fixes_to_source")
        return

    # Normalize line endings and ensure consistent formatting
    instructions = _dedent(instructions).strip()

    # Split into code chunk sections
    chunks = [c.strip() for c in re.split(r"\[Code Chunk\]", instructions) if c.strip()]

    repo_root = Path.cwd()

    for chunk in chunks:
        # Extract File: line
        m = re.search(r"File:\s*(.+)", chunk)
        if not m:
            print("Skipping chunk: no File: line found")
            continue
        raw_path = m.group(1).strip()

        # Some instruction producers include the repository name as a prefix; try to normalize
        candidate_paths = [raw_path]
        if raw_path.startswith("llm-debugger/"):
            candidate_paths.append(raw_path[len("llm-debugger/"):])
        if raw_path.startswith("./"):
            candidate_paths.append(raw_path[2:])

        target_path = None
        for p in candidate_paths:
            candidate = repo_root.joinpath(p)
            if candidate.exists():
                target_path = candidate
                break

        if target_path is None:
            # Try relative lookup ignoring any leading path segments (fallback)
            parts = Path(raw_path).parts
            for i in range(len(parts)):
                try_p = repo_root.joinpath(*parts[i:])
                if try_p.exists():
                    target_path = try_p
                    break

        if target_path is None:
            print(f"File not found for chunk: '{raw_path}' - skipped")
            continue

        # Extract Changed: and To: blocks
        changed_match = re.search(r"Changed:\s*(.*?)\s*(?:To:|\Z)", chunk, flags=re.S)
        to_match = re.search(r"To:\s*(.*?)(?:\n\s*\[Explanation\]|\Z)", chunk, flags=re.S)

        if not changed_match or not to_match:
            print(f"Chunk for '{target_path}' missing Changed:/To: blocks - skipped")
            continue

        changed_snippet = _dedent(changed_match.group(1)).strip('\n')
        new_snippet = _dedent(to_match.group(1)).strip('\n')

        if not changed_snippet:
            print(f"Empty 'Changed' snippet for {target_path} - skipped")
            continue

        # Read existing file content
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                file_text = f.read()
        except Exception as e:
            print(f"Failed to read {target_path}: {e}")
            continue

        # Try to locate the exact changed snippet in the file
        if changed_snippet in file_text:
            new_text = file_text.replace(changed_snippet, new_snippet, 1)
            already_applied = False
        else:
            # If exact match not found, check whether the new snippet is already present
            if new_snippet and new_snippet in file_text:
                print(f"Patch for {target_path} already applied - skipping")
                continue

            # Fallback: try a whitespace-normalized match
            def normalize(s: str) -> str:
                return re.sub(r"\s+", " ", s).strip()

            norm_changed = normalize(changed_snippet)
            norm_text = normalize(file_text)
            if norm_changed and norm_changed in norm_text:
                # Build a new normalized file and then attempt to map replacement naively
                # This is a best-effort fallback; if it fails, skip
                idx = norm_text.index(norm_changed)
                # Can't easily map back to original indices reliably; skip
                print(f"Found whitespace-normalized match for {target_path} but cannot safely apply - skipped")
                continue
            else:
                print(f"Original snippet not found in {target_path} - skipped")
                continue

        # Backup original file
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = target_path.with_suffix(target_path.suffix + f".bak_{ts}")
            with open(backup_path, 'w', encoding='utf-8') as bf:
                bf.write(file_text)
        except Exception as e:
            print(f"Failed to create backup for {target_path}: {e}")
            continue

        # Write the updated file
        try:
            with open(target_path, 'w', encoding='utf-8') as out:
                out.write(new_text)
            print(f"Applied patch to {target_path} (backup: {backup_path.name})")
        except Exception as e:
            print(f"Failed to write updated file {target_path}: {e}")
            # Attempt to restore from backup
            try:
                with open(backup_path, 'r', encoding='utf-8') as bf:
                    orig = bf.read()
                with open(target_path, 'w', encoding='utf-8') as out:
                    out.write(orig)
                print(f"Restored original from backup for {target_path}")
            except Exception:
                print(f"Failed to restore backup for {target_path} - manual intervention required")

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


