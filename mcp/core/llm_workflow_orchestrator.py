from __future__ import annotations

import inspect
import os
import sys
import traceback
from datetime import datetime
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .agent import LlmDebugAgent
from .debug_analysis_llm import (
    BlockInfo,
    DebugAnalysis,
    FailedTest,
    RuntimeStateSnapshot,
)
from .debug_types import BasicBlock, ExecutionAttempt, TestExecutionResult
from .dummy_cfg import get_dummy_blocks, get_dummy_sources
from .mcp_tools import build_runner_payload, run_with_block_tracing_subprocess
from .source_enhancement_llm import EnhancedSource
from .test_generation_llm import GeneratedTestCase, GeneratedTestSuite
from textwrap import dedent as _dedent
import asyncio
from . import mcp_routes
from pydantic_ai import Agent


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


def _is_valid_generated_test_case(
    case: GeneratedTestCase, target_function: str
) -> bool:
    """
    Best-effort static validation to avoid running obviously broken tests.
    """

    input_code = (case.input or "").lower()
    expected_code = (case.expected_output or "").lower()
    target_lower = (target_function or "").lower()

    has_result_assignment = "result =" in input_code
    references_result = "result" in expected_code
    calls_target = target_lower in input_code

    return has_result_assignment and references_result and calls_target


def _select_valid_test_index(
    suite: GeneratedTestSuite, preferred_index: int
) -> int:
    """
    Choose the first test that appears to call the target function and assign to result.
    """

    tests = suite.tests
    if not tests:
        raise ValueError("LLM did not return any generated tests.")

    if 0 <= preferred_index < len(tests):
        if _is_valid_generated_test_case(tests[preferred_index], suite.target_function):
            return preferred_index

    for idx, candidate in enumerate(tests):
        if _is_valid_generated_test_case(candidate, suite.target_function):
            return idx

    # Fall back to the preferred index if none pass validation.
    return max(0, min(preferred_index, len(tests) - 1))


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
    attempts: List[ExecutionAttempt]

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
    execute_all_tests: bool = False,
) -> LlmDebugRunResult:
    """
    End-to-end pipeline:
    1. Generate a suite of tests for the provided sources.
    2. Render a chosen test into executable Python.
    3. Run the test through the CFG tracer subprocess.
    4. Convert the trace into BlockInfo + RuntimeStateSnapshots.
    5. Ask the LLM to diagnose which blocks misbehaved.
    
    If execute_all_tests=True, executes all tests and generates instruction file.
    """
    
    if execute_all_tests:
        print("[orchestrator] execute_all_tests=True, executing all tests...", file=sys.stderr)
        test_results = run_all_tests_through_tracer_and_analyze(
            agent=agent,
            task_description=task_description,
            sources=sources,
            blocks=blocks,
        )
        
        # Generate instruction file
        original_sources = list(sources) if sources is not None else get_dummy_sources()
        instruction_filepath = generate_instruction_file_from_test_results(
            agent=agent,
            test_results=test_results,
            original_sources=original_sources,
            task_description=task_description,
        )
        print(f"[orchestrator] Instruction file generated: {instruction_filepath}", file=sys.stderr)
        
        # Return first result for backward compatibility
        return test_results[0] if test_results else run_generated_test_through_tracer_and_analyze(
            agent=agent,
            task_description=task_description,
            sources=sources,
            blocks=blocks,
            test_index=0,
            execute_all_tests=False,
        )

    source_entries = list(sources) if sources is not None else None
    if source_entries is None:
        print("[orchestrator] WARNING: sources is None, falling back to DUMMY sources", file=sys.stderr)
        source_entries = get_dummy_sources()
    else:
        print(f"[orchestrator] Received {len(source_entries)} source files", file=sys.stderr)

    if not source_entries:
        raise ValueError("No source files provided for test generation.")

    code_snippet = source_entries[0]["code"]
    suite = agent.generate_tests_for_code(code_snippet=code_snippet)

    if not suite.tests:
        raise ValueError("LLM did not return any generated tests.")
    if not (0 <= test_index < len(suite.tests)):
        raise IndexError(f"test_index {test_index} outside range of generated tests.")

    selected_index = _select_valid_test_index(suite, test_index)
    if selected_index != test_index:
        print(
            f"[orchestrator] selected test index {selected_index} instead of "
            f"preferred {test_index} due to validation heuristics."
        )

    test_case = suite.tests[selected_index]
    tests_code = render_generated_test_case_to_python(test_case, suite)

    # Enhance source code to be self-contained and executable
    print("[orchestrator] Enhancing source code for execution...", file=sys.stderr)
    # Log original source code for comparison
    for src in source_entries:
        print(f"[orchestrator] Original Code ({src['file_path']}):\n{src['code'][:500]}...", file=sys.stderr)

    enhanced_sources_list = agent.enhance_sources_for_execution(sources=source_entries)
    
    # Convert EnhancedSource objects back to Dict format for payload
    enhanced_source_entries = []
    for enhanced in enhanced_sources_list:
        print(
            f"[orchestrator] Enhanced {enhanced.file_path}: "
            f"added {len(enhanced.added_imports)} imports/stubs, "
            f"reasoning: {enhanced.reasoning[:100]}...",
            file=sys.stderr,
        )
        print(f"[orchestrator] Enhanced Code ({enhanced.file_path}):\n{enhanced.enhanced_code[:500]}...", file=sys.stderr)
        enhanced_source_entries.append({
            "file_path": enhanced.file_path,
            "code": enhanced.enhanced_code,
        })
    
    block_entries = list(blocks) if blocks is not None else None
    if block_entries is None:
        print("[orchestrator] WARNING: blocks is None, falling back to DUMMY blocks", file=sys.stderr)
        block_entries = get_dummy_blocks()
    else:
        print(f"[orchestrator] Received {len(block_entries)} blocks", file=sys.stderr)
    
    # Helper function to execute with enhanced sources
    def _execute_with_sources(sources_to_use: List[Dict[str, str]], attempt_num: int = 1) -> Dict[str, Any]:
        print(
            f"[orchestrator] Execution attempt {attempt_num} with {len(sources_to_use)} source file(s)",
            file=sys.stderr,
        )
        payload = build_runner_payload(
            sources=sources_to_use,
            blocks=block_entries,
            tests=tests_code,
        )
        print(
            f"[orchestrator] Building runner payload (attempt {attempt_num}):",
            {
                "sources_count": len(sources_to_use),
                "sources": [entry["file_path"] for entry in sources_to_use],
                "blocks_count": len(block_entries),
                "blocks": [block.block_id for block in block_entries],
                "tests_code_length": len(tests_code),
                "tests_code_preview": tests_code[:200],
            },
        )
        print(f"[orchestrator] Invoking block tracing subprocess (attempt {attempt_num})...", file=sys.stderr)
        trace_payload = run_with_block_tracing_subprocess(payload=payload)
        print(f"[orchestrator] Block tracing subprocess returned (attempt {attempt_num})", file=sys.stderr)
        return trace_payload
    
    # Iterative repair loop
    max_attempts = 5
    attempt_count = 0
    current_sources = enhanced_source_entries
    attempts_history: List[ExecutionAttempt] = []
    final_trace_payload = {}
    
    # Reason for the initial attempt (base enhancement)
    initial_reasoning = "Initial enhancement to add missing imports and stubs."
    if enhanced_sources_list:
        initial_reasoning = enhanced_sources_list[0].reasoning
    
    while attempt_count < max_attempts:
        attempt_count += 1
        
        # Execute
        trace_payload = _execute_with_sources(current_sources, attempt_num=attempt_count)
        final_trace_payload = trace_payload
        
        # Analyze result
        trace_entries = trace_payload.get("trace", []) or []
        error_info = trace_payload.get("error")
        source_loading_errors = trace_payload.get("source_loading_errors", [])
        stderr_text = trace_payload.get("stderr")
        
        is_success = not source_loading_errors and not error_info
        status = "success" if is_success else "error"
        
        # Construct error summary
        error_summary = None
        if source_loading_errors:
            error_summary = f"Source loading failed: {source_loading_errors[0].get('message')}"
        elif error_info:
            error_summary = f"Runtime error: {error_info.get('message')}"
            
        # Record attempt
        attempt = ExecutionAttempt(
            attempt_number=attempt_count,
            status=status,
            error_summary=error_summary,
            code_snapshot=current_sources,
            reasoning=initial_reasoning if attempt_count == 1 else None # Will be updated for subsequent attempts
        )
        
        # Update reasoning for the *previous* failed attempt that led to this one
        if attempt_count > 1:
            # The reasoning for this attempt comes from the fix applied after the previous failure
            # We'll capture that in the loop logic below, but strictly speaking 
            # the reasoning is associated with the fix generation.
            pass
            
        attempts_history.append(attempt)
        
        if is_success:
            # Generate success reasoning
            fixes_applied = []
            if attempt_count == 1:
                # First attempt - use initial enhancement reasoning
                if enhanced_sources_list:
                    for enhanced in enhanced_sources_list:
                        if enhanced.added_imports:
                            fixes_applied.append(f"Added imports/stubs: {', '.join(enhanced.added_imports)}")
                        if enhanced.reasoning and enhanced.reasoning != initial_reasoning:
                            fixes_applied.append(enhanced.reasoning)
            else:
                # Subsequent attempts - use fix reasoning from previous attempts
                if initial_reasoning and initial_reasoning != "Initial enhancement to add missing imports and stubs.":
                    fixes_applied.append(initial_reasoning)
            
            if not fixes_applied:
                fixes_applied = ["Code executed successfully without errors"]
            
            success_reasoning = f"Test passed successfully. Key fixes applied: {'; '.join(fixes_applied)}. The code now correctly handles the test scenario."
            
            # Update the attempt with success reasoning
            attempt.reasoning = success_reasoning
            attempts_history[-1] = attempt  # Update the last attempt
            
            print(f"[orchestrator] Attempt {attempt_count} succeeded!", file=sys.stderr)
            print(f"[orchestrator] Success reasoning: {success_reasoning}", file=sys.stderr)
            break
            
        # If we failed and have retries left, try to fix
        if attempt_count < max_attempts:
            print(
                f"[orchestrator] Attempt {attempt_count} failed. Enhancing with error context...",
                file=sys.stderr,
            )
            
            # Combine all errors for context
            context_errors = source_loading_errors or []
            if error_info:
                context_errors.append(error_info)
                
            # Log source before re-enhancement
            for src in source_entries:
                print(f"[orchestrator] Source before re-enhancement ({src['file_path']}):\n{src['code'][:200]}...", file=sys.stderr)

            re_enhanced_sources_list = agent.enhance_sources_for_execution(
                sources=source_entries,  # Always start from base sources to apply cumulative fixes cleanly
                error_context=context_errors,
            )
            
            # Update current sources
            current_sources = []
            fix_reasoning = []
            for enhanced in re_enhanced_sources_list:
                current_sources.append({
                    "file_path": enhanced.file_path,
                    "code": enhanced.enhanced_code,
                })
                fix_reasoning.append(enhanced.reasoning)
                print(f"[orchestrator] Re-enhanced Code ({enhanced.file_path}):\n{enhanced.enhanced_code[:500]}...", file=sys.stderr)
            
            # Store reasoning on the current attempt record (which failed) to explain the *next* attempt
            # Or store it on the next attempt? Let's store it on the next attempt.
            # Actually, ExecutionAttempt has 'reasoning' field which we defined as "why this fix was applied".
            # So for the next attempt object created, we want this reasoning.
            initial_reasoning = "; ".join(fix_reasoning) 

    # --- End of loop ---

    # Prepare final results based on the last attempt (or successful one)
    trace_entries = final_trace_payload.get("trace", []) or []
    error_info = final_trace_payload.get("error")
    source_loading_errors = final_trace_payload.get("source_loading_errors", [])
    stderr_text = final_trace_payload.get("stderr")
    
    print(
        f"[orchestrator] trace_entries count: {len(trace_entries)}, "
        f"error_info: {error_info}",
    )
    
    # Log errors
    if source_loading_errors:
        for err in source_loading_errors:
            print(f"[orchestrator] Source error: {err.get('message')}", file=sys.stderr)
    if error_info:
         print(f"[orchestrator] Runtime error: {error_info.get('message')}", file=sys.stderr)
    
    if stderr_text:
        print("[orchestrator] runner stderr:\n", stderr_text)

    # Use current_sources (which may have been re-enhanced) for block lookup
    block_lookup = _build_block_info_lookup(block_entries, current_sources)
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
        # ... (existing fallback logic for no trace) ...
        trace_block_ids = [
            entry.get("block_id")
            for entry in trace_entries
            if entry.get("block_id") is not None
        ]
        
        # Logic to determine actual description and notes (reused from existing)
        if source_loading_errors:
             decorator_errors = [e for e in source_loading_errors if e.get("error_type") == "decorator_framework_error"]
             if decorator_errors:
                 actual_description = (
                     f"Source code failed to load due to framework decorator errors. "
                     f"Files affected: {', '.join(e['file_path'] for e in decorator_errors)}. "
                     f"Framework stubs were provided but may need additional objects. "
                     f"Original error: {decorator_errors[0].get('message', 'Unknown')}"
                 )
                 notes = decorator_errors[0].get("traceback")
             else:
                 actual_description = (
                     f"Source code failed to load. "
                     f"Errors: {source_loading_errors[0].get('message', 'Unknown error')}"
                 )
                 notes = source_loading_errors[0].get("traceback")
        elif error_info:
            actual_description = error_info.get("message", "Test failed before executing any code blocks")
            notes = error_info.get("traceback")
        else:
            actual_description = "Test failed before executing any code blocks"
            notes = None
        
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
            ),
            failed_test=failed_test,
            assessments=[],
        )
        
        fallback_blocks: List[BlockInfo] = [
            block_lookup[block.block_id]
            for block in block_entries
            if block.block_id in block_lookup
        ]

        return LlmDebugRunResult(
            suite=suite,
            test_case=test_case,
            trace_payload=final_trace_payload,
            debug_analysis=debug_analysis,
            blocks=fallback_blocks,
            runtime_states=[],
            attempts=attempts_history,
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
        trace_payload=final_trace_payload,
        debug_analysis=debug_analysis,
        blocks=block_infos,
        runtime_states=runtime_states,
        attempts=attempts_history,
    )


def run_all_tests_through_tracer_and_analyze(
    *,
    agent: LlmDebugAgent,
    task_description: str,
    sources: Sequence[Dict[str, str]] | None = None,
    blocks: Sequence[BasicBlock] | None = None,
) -> List[LlmDebugRunResult]:
    """
    Execute all tests in the generated test suite and collect results.
    
    Args:
        agent: LlmDebugAgent for LLM calls
        task_description: Human-readable task description
        sources: Optional list of source files
        blocks: Optional list of BasicBlock objects
        
    Returns:
        List of LlmDebugRunResult objects, one per test
    """
    print("[orchestrator] Executing all tests in suite...", file=sys.stderr)
    
    source_entries = list(sources) if sources is not None else None
    if source_entries is None:
        print("[orchestrator] WARNING: sources is None, falling back to DUMMY sources", file=sys.stderr)
        source_entries = get_dummy_sources()
    
    if not source_entries:
        raise ValueError("No source files provided for test generation.")
    
    code_snippet = source_entries[0]["code"]
    suite = agent.generate_tests_for_code(code_snippet=code_snippet)
    
    if not suite.tests:
        raise ValueError("LLM did not return any generated tests.")
    
    print(f"[orchestrator] Generated {len(suite.tests)} tests, executing all...", file=sys.stderr)
    
    results: List[LlmDebugRunResult] = []
    for test_idx in range(len(suite.tests)):
        print(f"[orchestrator] Executing test {test_idx + 1}/{len(suite.tests)}: {suite.tests[test_idx].name}", file=sys.stderr)
        try:
            result = run_generated_test_through_tracer_and_analyze(
                agent=agent,
                task_description=task_description,
                sources=sources,
                blocks=blocks,
                test_index=test_idx,
            )
            results.append(result)
        except Exception as e:
            print(f"[orchestrator] Error executing test {test_idx}: {e}", file=sys.stderr)
            # Create a failed result for this test
            failed_test = FailedTest(
                name=suite.tests[test_idx].name,
                input=suite.tests[test_idx].input,
                expected=suite.tests[test_idx].expected_output,
                actual=f"Test execution failed: {str(e)}",
                notes=traceback.format_exc(),
            )
            debug_analysis = DebugAnalysis(
                task_description=f"Test '{suite.tests[test_idx].name}' failed to execute.",
                failed_test=failed_test,
                assessments=[],
            )
            results.append(
                LlmDebugRunResult(
                    suite=suite,
                    test_case=suite.tests[test_idx],
                    trace_payload={"ok": False, "error": {"message": str(e)}},
                    debug_analysis=debug_analysis,
                    blocks=[],
                    runtime_states=[],
                    attempts=[],
                )
            )
    
    print(f"[orchestrator] Completed execution of {len(results)} tests", file=sys.stderr)
    return results


def build_fix_instruction_prompt(
    passed_tests: List[LlmDebugRunResult],
    failed_tests: List[LlmDebugRunResult],
    original_sources: List[Dict[str, str]],
    task_description: str,
) -> str:
    """
    Build a prompt for generating detailed fix instructions.
    """
    # Format original code chunks
    code_chunks_section = []
    for src in original_sources:
        file_path = src.get("file_path", "unknown.py")
        code = src.get("code", "")
        # Try to extract line numbers from code if available
        code_chunks_section.append(f"[Code Chunk]\nFile: {file_path}\n```python\n{code}\n```\n")
    
    # Format passed tests
    passed_tests_section = []
    for result in passed_tests:
        test_case = result.test_case
        success_reasoning = ""
        if result.attempts:
            last_attempt = result.attempts[-1]
            if last_attempt.status == "success" and last_attempt.reasoning:
                success_reasoning = f"\nSuccess Reasoning: {last_attempt.reasoning}"
        passed_tests_section.append(
            f"Test: {test_case.name}\n"
            f"Input: {test_case.input}\n"
            f"Expected: {test_case.expected_output}\n"
            f"Status: PASSED{success_reasoning}\n"
        )
    
    # Format failed tests
    failed_tests_section = []
    for result in failed_tests:
        test_case = result.test_case
        failed_test = result.debug_analysis.failed_test
        failed_tests_section.append(
            f"Test: {test_case.name}\n"
            f"Input: {test_case.input}\n"
            f"Expected: {test_case.expected_output}\n"
            f"Actual: {failed_test.actual}\n"
            f"Error: {failed_test.notes or 'N/A'}\n"
            f"Status: FAILED\n"
        )
    
    # Format execution history
    execution_history = []
    for result in failed_tests:
        if result.attempts:
            for attempt in result.attempts:
                execution_history.append(f"Attempt {attempt.attempt_number}: {attempt.reasoning or attempt.error_summary or 'N/A'}")
    
    prompt = f"""
You are analyzing test results to generate detailed fix instructions for debugging code.

[Task Description]
{task_description}

[Original Code Context]
{chr(10).join(code_chunks_section)}

[Intent]
The code is intended to: {task_description}

[Passed Tests - Examples of Working Behavior]
{chr(10).join(passed_tests_section) if passed_tests_section else "No tests passed."}

[Failed Tests - Issues to Fix]
{chr(10).join(failed_tests_section) if failed_tests_section else "No tests failed."}

[Execution History]
{chr(10).join(execution_history) if execution_history else "No execution history available."}

Your task: Generate detailed fix instructions that explain:
1. WHAT TO DO: Specific code changes needed to fix the failing tests
2. WHERE TO DO IT: File paths and line numbers for each change
3. WHAT NOT TO DO: Things to avoid, patterns that don't work (based on execution history)
4. Reasoning: Why these fixes are needed based on test results

CRITICAL: 
- Preserve behavior that makes passed tests work
- Fix issues that cause failed tests
- Avoid repeating fixes that were already tried (see execution history)
- Provide clear before/after code snippets for each fix

Format your response as structured text following this format:

[Fix Instructions]
WHAT TO DO:
- <specific change 1>
- <specific change 2>

WHERE TO DO IT:
- File: <file_path>, Lines: <start>-<end>
- File: <file_path>, Lines: <start>-<end>

WHAT NOT TO DO:
- <anti-pattern 1>
- <anti-pattern 2>

[Code Changes]
File: <file_path>
Lines: <start>-<end>

Changed:
<old code>

To:
<new code>

[Reasoning]
<why this change fixes the failing tests while preserving passed tests>
"""
    return dedent(prompt).strip()


def generate_fix_instructions(
    *,
    agent: Agent,
    passed_tests: List[LlmDebugRunResult],
    failed_tests: List[LlmDebugRunResult],
    original_sources: List[Dict[str, str]],
    task_description: str,
) -> str:
    """
    Generate fix instructions using LLM.
    """
    prompt = build_fix_instruction_prompt(
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        original_sources=original_sources,
        task_description=task_description,
    )
    try:
        # Log Groq call location for debugging tool_use_failed errors
        stack = inspect.stack()
        caller_frame = stack[0]  # Current frame (this logging line)
        # Get the actual line number where run_sync is called (next line)
        call_line = caller_frame.lineno + 1
        caller_info = f"File: {__file__}, Line: {call_line}, Function: {caller_frame.function}, Output Type: unstructured (text only)"
        print(f"[groq_call] {caller_info}", file=sys.stderr)
        run_result = agent.run_sync(prompt)  # Text output, not structured
        instructions = run_result.output
        print(f"[orchestrator] Generated fix instructions ({len(instructions)} chars)", file=sys.stderr)
        return instructions
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"[groq_error] Function: generate_fix_instructions, Error Type: {error_type}, Message: {error_msg}", file=sys.stderr)
        if hasattr(e, 'status_code'):
            print(f"[groq_error] HTTP Status: {e.status_code}", file=sys.stderr)
        if hasattr(e, 'response'):
            print(f"[groq_error] Response: {e.response}", file=sys.stderr)
        print(f"[groq_error] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        # Return fallback instructions
        return f"[Fix Instructions]\nError generating instructions: {error_msg}\n\nPlease review the test results manually."


def generate_instruction_file_from_test_results(
    *,
    agent: LlmDebugAgent,
    test_results: List[LlmDebugRunResult],
    original_sources: Sequence[Dict[str, str]],
    task_description: str,
    output_dir: str = "instructions",  # Matches debug_fix_instructions.py default
) -> str:
    """
    Generate instruction file from test results.
    
    Args:
        agent: LlmDebugAgent for LLM calls
        test_results: List of test execution results
        original_sources: Original source files (before enhancement)
        task_description: Task description
        output_dir: Directory to save instruction file
        
    Returns:
        Filepath of generated instruction file
    """
    print(f"[orchestrator] Generating instruction file from {len(test_results)} test results...", file=sys.stderr)
    
    # Separate passed vs failed tests
    passed_tests: List[LlmDebugRunResult] = []
    failed_tests: List[LlmDebugRunResult] = []
    
    for result in test_results:
        trace_payload = result.trace_payload
        error_info = trace_payload.get("error")
        source_loading_errors = trace_payload.get("source_loading_errors", [])
        
        is_passed = trace_payload.get("ok", False) and not source_loading_errors and not error_info
        if is_passed:
            passed_tests.append(result)
        else:
            failed_tests.append(result)
    
    print(f"[orchestrator] Separated tests: {len(passed_tests)} passed, {len(failed_tests)} failed", file=sys.stderr)
    
    # Generate fix instructions using LLM
    original_sources_list = list(original_sources)
    instructions_text = generate_fix_instructions(
        agent=agent.agent,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        original_sources=original_sources_list,
        task_description=task_description,
    )
    
    # Build instruction content following send_debugger_response pattern
    # Get task description in the same format as send_debugger_response
    task_description_section = f"""
Apply suggested fixes to the codebase.
A separate debugging pipeline has already identified:

Which test cases failed
The root cause analysis
Exact file names and line numbers involved
Proposed minimal fixes
Relevant diffs, stack traces, and context
Your job is to apply only the changes required to fix the issues, following these rules:

1. Editing Rules

Modify only files explicitly listed in the input.
For each file, apply the changes inside the input.
If a patch is ambiguous, ask for clarification instead of guessing.
Do not rewrite entire files unless the patch requires it.
Preserve formatting, imports, comments, and style of the existing codebase.
Never introduce new dependencies unless the patch explicitly instructs it.

2. Consistency Rules

Ensure all changes type-check and satisfy the project's conventions.
Ensure each fix is coherent with the runtime trace and failing test behavior.
If a patch interacts with a function called across multiple files, verify cross-file compatibility.
If removing or refactoring code, ensure references and calls remain valid.

3. Safety Rules

Do not create new files unless explicitly instructed.
Do not delete or rename files unless explicitly instructed.
Avoid speculative changes; stay strictly within the proposed patches.
If you need more context from a file, request it before editing.
"""
    
    # Build the full instruction content (matching send_debugger_response pattern: task_description + '\n' + instructions)
    instruction_file_content = task_description_section + '\n' + f"""[Original Code Context]
{chr(10).join(f"File: {src.get('file_path', 'unknown.py')}\n```python\n{src.get('code', '')}\n```" for src in original_sources_list)}

[Intent]
{task_description}

[Passed Tests - Examples of Working Behavior]
{chr(10).join(f"Test: {result.test_case.name}\nInput: {result.test_case.input}\nExpected: {result.test_case.expected_output}\nStatus: PASSED\nSuccess Reasoning: {result.attempts[-1].reasoning if result.attempts and result.attempts[-1].reasoning else 'N/A'}\n" for result in passed_tests) if passed_tests else "No tests passed."}

[Failed Tests - Issues to Fix]
{chr(10).join(f"Test: {result.test_case.name}\nInput: {result.test_case.input}\nExpected: {result.test_case.expected_output}\nActual: {result.debug_analysis.failed_test.actual}\nError: {result.debug_analysis.failed_test.notes or 'N/A'}\nStatus: FAILED\n" for result in failed_tests) if failed_tests else "No tests failed."}

[Execution History]
{chr(10).join(f"Attempt {attempt.attempt_number}: {attempt.reasoning or attempt.error_summary or 'N/A'}" for result in failed_tests for attempt in result.attempts) if failed_tests else "No execution history."}

{instructions_text}
"""
    
    # Ensure output directory exists (same pattern as send_debugger_response in debug_fix_instructions.py)
    print(f"[orchestrator] Ensuring output directory exists: {output_dir}", file=sys.stderr)
    os.makedirs(output_dir, exist_ok=True)
    if os.path.exists(output_dir):
        print(f"[orchestrator] Output directory verified: {output_dir}", file=sys.stderr)
    else:
        print(f"[orchestrator] ERROR: Output directory does not exist after creation: {output_dir}", file=sys.stderr)
    
    # Generate filename with timestamp (exact same format as debug_fix_instructions.py: YYYY-MM-DD_HH-MM.txt)
    # Matches: timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M") and filename = f"{timestamp}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)
    print(f"[orchestrator] Generated instruction file path: {filepath}", file=sys.stderr)
    print(f"[orchestrator] Instruction file content length: {len(instruction_file_content)} characters", file=sys.stderr)
    
    # Write instruction file (same pattern as send_debugger_response)
    try:
        print(f"[orchestrator] Opening file for writing: {filepath}", file=sys.stderr)
        with open(filepath, 'w', encoding='utf-8') as f:
            bytes_written = f.write(instruction_file_content)
            print(f"[orchestrator] Wrote {bytes_written} characters to file", file=sys.stderr)
        
        # Verify file was written
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"[orchestrator] Instruction file saved successfully: {filepath} (size: {file_size} bytes)", file=sys.stderr)
        else:
            print(f"[orchestrator] ERROR: File does not exist after write: {filepath}", file=sys.stderr)
    except Exception as e:
        print(f"[orchestrator] ERROR: Failed to write instruction file: {e}", file=sys.stderr)
        print(f"[orchestrator] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        raise
    
    return filepath


def build_static_cfg_from_blocks(
    blocks: Sequence[BasicBlock],
    sources: Sequence[Dict[str, str]] | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a static CFG representation (nodes + edges) without requiring runtime data.

    Args:
        blocks: BasicBlock definitions describing the CFG.
        sources: Optional source entries (file_path/code) so we can attach snippets.

    Returns:
        Dict with `nodes` and `edges` lists that match the frontend's expectations.
    """

    block_lookup = (
        _build_block_info_lookup(blocks, sources or [])
        if sources is not None
        else {block.block_id: BlockInfo(id=block.block_id, code="", file_path=block.file_path,
                                        start_line=block.start_line, end_line=block.end_line) for block in blocks}
    )

    nodes: List[Dict[str, Any]] = []
    for block in blocks:
        block_info = block_lookup.get(block.block_id)
        nodes.append(
            {
                "id": block.block_id,
                "type": "cfgNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "blockId": block.block_id,
                    "blockName": block.block_id,
                    "codeSnippet": block_info.code if block_info else "",
                    "status": "pending",
                    "file": block.file_path,
                    "lineStart": block.start_line,
                    "lineEnd": block.end_line,
                    "executionCount": 0,
                },
            }
        )

    edges: List[Dict[str, Any]] = []
    prev_block_for_file: Dict[str, str] = {}
    sorted_blocks = sorted(
        blocks,
        key=lambda block: ((block.file_path or ""), block.start_line or 0),
    )
    for block in sorted_blocks:
        file_path = block.file_path or ""
        prev_block = prev_block_for_file.get(file_path)
        if prev_block:
            edges.append(
                {
                    "id": f"edge-{prev_block}-{block.block_id}",
                    "source": prev_block,
                    "target": block.block_id,
                }
            )
        prev_block_for_file[file_path] = block.block_id

    return {"nodes": nodes, "edges": edges}


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

    has_runtime_steps = len(steps) > 0
    nodes: List[Dict[str, Any]] = []
    for block in run_result.blocks:
        block_id = block.id
        default_status = "succeeded" if has_runtime_steps else "pending"
        node_status = "failed" if block_id in incorrect_blocks else default_status
        nodes.append(
            {
                "id": block_id,
                "type": "cfgNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "blockId": block_id,
                    "blockName": block_id,
                    "codeSnippet": block.code,
                    "status": node_status,
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
        "attempts": [a.to_dict() for a in run_result.attempts],
    }
