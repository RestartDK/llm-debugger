"""
Multi-file LDB methodology compliance test.

Validates that the pipeline:
1. Builds CFG/basic-block metadata across multiple files (Profiling step).
2. Runs the tracer to capture runtime locals per block (Profiling step).
3. Sends blocks + runtime states to the LLM for per-block assessments (Debugging step).
4. Produces UI payload artifacts for visualization/regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

from core.agent import LlmDebugAgent
from core.debug_types import BasicBlock
from core.llm_workflow_orchestrator import (
    build_debugger_ui_payload,
    run_generated_test_through_tracer_and_analyze,
)


def build_example_sources() -> Dict[str, str]:
    """
    Construct a tiny multi-file project representing a real bug:
    - `text_utils.py` has an off-by-one style regex issue (matches exactly 4 chars).
    - `analyzer.py` imports that helper and aggregates results.
    """

    text_utils = """
import re


def find_char_long(text: str):
    \"""
    Return words that are at least four characters long using regex.
    \"""
    if text == " ":
        return []

    # BUG: pattern only matches exactly four characters, not >= 4.
    pat = r"\\b\\w{4}\\b"
    res = re.findall(pat, text)
    return res
"""

    analyzer = """
from text_utils import find_char_long


def analyze_text_for_long_words(text: str):
    \"""
    Call into text_utils.find_char_long and return stats.
    \"""
    words = find_char_long(text)
    return {
        "count": len(words),
        "words": words,
    }
"""

    return {
        "text_utils.py": text_utils,
        "analyzer.py": analyzer,
    }


def build_basic_blocks_for_sources(files_dict: Dict[str, str]) -> List[BasicBlock]:
    """
    Build BasicBlocks with end_line values that correspond to executable lines.
    
    The tracer records when execution hits a block's end_line, so we need
    end_line values that will actually be executed (e.g., return statements).
    This ensures the tracer captures trace entries for each block.
    """

    blocks: List[BasicBlock] = []
    
    for file_path, code in files_dict.items():
        lines = code.splitlines()
        stem = Path(file_path).stem
        
        # Find all return statement lines (these are guaranteed to be executed)
        return_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Match return statements (but not in comments or docstrings)
            if stripped.startswith("return ") or stripped == "return":
                return_lines.append(i)
        
        if not return_lines:
            # No return statements found - use the last line as fallback
            # This is a fallback, but may not work if execution doesn't reach the end
            blocks.append(
                BasicBlock(
                    block_id=f"{stem}:block-0",
                    file_path=file_path,
                    start_line=1,
                    end_line=len(lines),
                )
            )
        elif len(return_lines) == 1:
            # Single return statement - create one block ending at that return
            blocks.append(
                BasicBlock(
                    block_id=f"{stem}:block-0",
                    file_path=file_path,
                    start_line=1,
                    end_line=return_lines[0],
                )
            )
        else:
            # Multiple return statements - create blocks for each path
            # First block: from start to first return (early return path)
            blocks.append(
                BasicBlock(
                    block_id=f"{stem}:block-0",
                    file_path=file_path,
                    start_line=1,
                    end_line=return_lines[0],
                )
            )
            # Second block: from after first return to final return (main path)
            blocks.append(
                BasicBlock(
                    block_id=f"{stem}:block-1",
                    file_path=file_path,
                    start_line=return_lines[0] + 1,
                    end_line=return_lines[-1],
                )
            )
    
    return blocks


def test_ldb_methodology_multi_file() -> bool:
    """
    End-to-end validation of the LDB pipeline using multiple files.
    """

    print("=" * 80)
    print("Step 0: Build multi-file example project")
    print("=" * 80)

    files_dict = build_example_sources()
    for path in files_dict:
        print(f"  ✓ Added source file: {path}")

    sources = [{"file_path": path, "code": code} for path, code in files_dict.items()]

    print("\n" + "=" * 80)
    print("Step 1: Profiling — Basic block setup across files")
    print("=" * 80)

    blocks = build_basic_blocks_for_sources(files_dict)
    for block in blocks:
        print(
            f"  • {block.file_path} — BasicBlock(id={block.block_id}, "
            f"lines {block.start_line}-{block.end_line})"
        )

    block_files = sorted({block.file_path for block in blocks})
    print(f"  ✓ Extracted {len(blocks)} basic blocks across files: {block_files}")

    print("\n" + "=" * 80)
    print("Step 2: Profiling — Run tracer + capture runtime locals")
    print("=" * 80)

    agent = LlmDebugAgent()
    task_description = (
        "Find all words with length >= 4 by combining text_utils + analyzer modules."
    )

    try:
        run_result = run_generated_test_through_tracer_and_analyze(
            agent=agent,
            task_description=task_description,
            sources=sources,
            blocks=blocks,
            test_index=0,
        )
    except Exception as exc:  # pragma: no cover - diagnostic output
        print(f"✗ Error while executing traced test: {exc}")
        import traceback

        traceback.print_exc()
        return False

    trace_entries = run_result.trace_payload.get("trace") or []
    print(f"  ✓ Trace entries captured: {len(trace_entries)}")
    print(f"  ✓ Runtime snapshots collected: {len(run_result.runtime_states)}")

    print("\n" + "=" * 80)
    print("Step 3: Debugging — LLM per-block assessments")
    print("=" * 80)

    assessments = run_result.debug_analysis.assessments
    incorrect = [a for a in assessments if not a.correct]
    correct = [a for a in assessments if a.correct]
    print(f"  ✓ Total block assessments: {len(assessments)}")
    print(f"    • Correct blocks:   {len(correct)}")
    print(f"    • Incorrect blocks: {len(incorrect)}")

    for idx, assessment in enumerate(assessments):
        status = "INCORRECT" if not assessment.correct else "CORRECT"
        print(f"\n  [BLOCK-{idx}] {assessment.block}")
        print(f"    Status: {status}")
        print(f"    Explanation: {assessment.explanation}")

    print("\n" + "=" * 80)
    print("Step 4: Compliance checks")
    print("=" * 80)

    checks = {
        "CFG covers multiple files": len(block_files) >= 2,
        "Trace captured": len(trace_entries) > 0,
        "Runtime snapshots per analyzed block": (
            len(run_result.runtime_states) == len(run_result.blocks)
        ),
        "LLM produced assessments": len(assessments) > 0,
        "Assessments include explanations": all(
            bool(a.explanation) for a in assessments
        ),
        "Runtime snapshots include locals": all(
            isinstance(s.before, dict) and isinstance(s.after, dict)
            for s in run_result.runtime_states
        ),
    }

    all_passed = all(checks.values())
    for label, passed in checks.items():
        mark = "✓" if passed else "✗"
        print(f"  {mark} {label}")

    print("\n" + "=" * 80)
    print("Step 5: UI payload export (for visualization/regeneration)")
    print("=" * 80)

    try:
        ui_payload = build_debugger_ui_payload(run_result)
        print("  ✓ UI payload generated")
        print(f"    • Steps:     {len(ui_payload['steps'])}")
        print(f"    • Problems:  {len(ui_payload['problems'])}")
        print(f"    • CFG nodes: {len(ui_payload['nodes'])}")
        print(f"    • CFG edges: {len(ui_payload['edges'])}")
    except Exception as exc:  # pragma: no cover - diagnostic output
        print(f"✗ Failed to build UI payload: {exc}")
        all_passed = False

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    if all_passed:
        print("✓ Multi-file LDB methodology test PASSED.")
    else:
        print("✗ Multi-file LDB methodology test FAILED — see output above.")

    return all_passed


if __name__ == "__main__":
    success = test_ldb_methodology_multi_file()
    sys.exit(0 if success else 1)


