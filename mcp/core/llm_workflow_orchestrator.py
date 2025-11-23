from __future__ import annotations

import ast
import sys
import time
import traceback
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
from .debug_types import BasicBlock
from .dummy_cfg import get_dummy_blocks, get_dummy_sources
from .mcp_tools import build_runner_payload, run_with_block_tracing_subprocess
from .test_generation_llm import GeneratedTestCase, GeneratedTestSuite
from textwrap import dedent as _dedent
import asyncio
from . import mcp_routes


def extract_function_from_code(
    code: str, function_name: Optional[str] = None, start_line: Optional[int] = None, end_line: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Extract a complete function definition from code.
    
    Args:
        code: Source code to parse
        function_name: Optional function name to search for
        start_line: Optional start line hint (1-indexed)
        end_line: Optional end line hint (1-indexed)
    
    Returns:
        Dict with keys: 'code', 'name', 'signature', 'dependencies', 'line_start', 'line_end'
        or None if function not found
    """
    try:
        tree = ast.parse(code)
        
        # If we have line hints, extract code from that range
        if start_line and end_line:
            lines = code.split('\n')
            if 1 <= start_line <= len(lines) and 1 <= end_line <= len(lines):
                extracted_code = '\n'.join(lines[start_line - 1:end_line])
                # Try to parse just this section
                try:
                    section_tree = ast.parse(extracted_code)
                    for node in ast.walk(section_tree):
                        if isinstance(node, ast.FunctionDef):
                            func_code = ast.get_source_segment(code, node) or extracted_code
                            return {
                                'code': func_code,
                                'name': node.name,
                                'signature': ast.unparse(node.args) if hasattr(ast, 'unparse') else str(node.args),
                                'dependencies': _extract_dependencies(node),
                                'line_start': node.lineno,
                                'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                            }
                except SyntaxError:
                    # If parsing fails, return the raw code snippet
                    return {
                        'code': extracted_code,
                        'name': function_name or 'unknown',
                        'signature': '',
                        'dependencies': [],
                        'line_start': start_line,
                        'line_end': end_line,
                    }
        
        # Otherwise, search for function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if function_name is None or node.name == function_name:
                    func_code = ast.get_source_segment(code, node) or code
                    return {
                        'code': func_code,
                        'name': node.name,
                        'signature': ast.unparse(node.args) if hasattr(ast, 'unparse') else str(node.args),
                        'dependencies': _extract_dependencies(node),
                        'line_start': node.lineno,
                        'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                    }
        
        return None
    except SyntaxError as e:
        print(f"[orchestrator] WARNING: Could not parse code for function extraction: {e}", file=sys.stderr)
        # Return raw code snippet if parsing fails
        if start_line and end_line:
            lines = code.split('\n')
            if 1 <= start_line <= len(lines) and 1 <= end_line <= len(lines):
                return {
                    'code': '\n'.join(lines[start_line - 1:end_line]),
                    'name': function_name or 'unknown',
                    'signature': '',
                    'dependencies': [],
                    'line_start': start_line,
                    'line_end': end_line,
                }
        return None
    except Exception as e:
        print(f"[orchestrator] ERROR extracting function: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"[orchestrator] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        return None


def _extract_dependencies(node: ast.AST) -> List[str]:
    """Extract dependencies (imports, names) from an AST node."""
    dependencies = []
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                dependencies.append(alias.name)
        elif isinstance(child, ast.ImportFrom):
            if child.module:
                dependencies.append(child.module)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            # This is a name being used (not defined)
            dependencies.append(child.id)
    return list(set(dependencies))  # Remove duplicates


def render_generated_test_case_to_python(
    case: GeneratedTestCase, suite: GeneratedTestSuite
) -> str:
    """
    Render a GeneratedTestCase into runnable Python code.

    The prompt should ensure `case.input` contains the code that prepares inputs
    and calls the target under test, while `case.expected_output` contains the
    assertions that must hold.
    Includes mock setup code if provided.
    """

    header = dedent(
        f"""
        # LLM-generated test: {case.name}
        # Target scope: {suite.target_function}
        # Description: {case.description}
        """
    ).strip()

    # Include mock setup if provided
    parts = [header]
    if case.mock_setup:
        parts.append(case.mock_setup)
    if case.input:
        parts.append(case.input)
    if case.expected_output:
        parts.append(case.expected_output)

    return "\n\n".join(
        part.strip() for part in parts if part and part.strip()
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
    execution_log: Optional[List[Dict[str, Any]]] = None

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
    pipeline_start_time = time.time()
    execution_log: List[Dict[str, Any]] = []
    
    def log_step(step_name: str, message: str, data: Optional[Dict[str, Any]] = None):
        elapsed = time.time() - pipeline_start_time
        log_entry = {
            'timestamp': elapsed,
            'step': step_name,
            'message': message,
        }
        if data:
            log_entry['data'] = data
        execution_log.append(log_entry)
        print(f"[orchestrator] [{step_name}] ({elapsed:.2f}s) {message}", file=sys.stderr)
        if data:
            print(f"[orchestrator] [{step_name}] Data: {data}", file=sys.stderr)

    try:
        log_step("init", "Starting test execution pipeline", {
            'task_description': task_description,
            'blocks_count': len(blocks) if blocks else 0,
            'sources_count': len(sources) if sources else 0,
        })

        source_entries = list(sources) if sources is not None else get_dummy_sources()
        if not source_entries:
            raise ValueError("No source files provided for test generation.")

        # Extract function code from blocks if available
        code_snippet = source_entries[0]["code"]
        target_function = None
        extracted_function = None
        
        if blocks and len(blocks) > 0:
            # Try to extract function from first block
            first_block = blocks[0]
            log_step("extract", f"Extracting function from block {first_block.block_id}", {
                'file_path': first_block.file_path,
                'start_line': first_block.start_line,
                'end_line': first_block.end_line,
            })
            
            extracted_function = extract_function_from_code(
                code_snippet,
                function_name=None,  # We don't know the function name yet
                start_line=first_block.start_line,
                end_line=first_block.end_line
            )
            
            if extracted_function:
                code_snippet = extracted_function['code']
                target_function = extracted_function['name']
                log_step("extract", f"Extracted function: {target_function}", {
                    'dependencies': extracted_function.get('dependencies', []),
                    'code_length': len(code_snippet),
                })
            else:
                log_step("extract", "Could not extract function, using full code snippet", {
                    'code_length': len(code_snippet),
                })

        log_step("test_gen", "Generating test cases", {
            'target_function': target_function,
            'code_snippet_length': len(code_snippet),
        })
        
        suite = agent.generate_tests_for_code(
            code_snippet=code_snippet,
            target_function=target_function
        )
        
        log_step("test_gen", f"Generated {len(suite.tests)} test case(s)", {
            'target_function': suite.target_function,
            'test_style': suite.test_style,
        })

        if not suite.tests:
            raise ValueError("LLM did not return any generated tests.")
        if not (0 <= test_index < len(suite.tests)):
            raise IndexError(f"test_index {test_index} outside range of generated tests.")

        selected_index = _select_valid_test_index(suite, test_index)
        if selected_index != test_index:
            log_step("test_select", f"Selected test index {selected_index} instead of preferred {test_index}")

        test_case = suite.tests[selected_index]
        log_step("test_render", f"Rendering test case: {test_case.name}", {
            'has_mock_setup': bool(test_case.mock_setup),
            'dependencies': test_case.dependencies or [],
        })
        
        tests_code = render_generated_test_case_to_python(test_case, suite)
        log_step("test_render", "Test code rendered", {
            'test_code_length': len(tests_code),
            'preview': tests_code[:200],
        })

        block_entries = list(blocks) if blocks is not None else get_dummy_blocks()
        log_step("payload_build", "Building runner payload", {
            'sources_count': len(source_entries),
            'blocks_count': len(block_entries),
        })
        
        payload = build_runner_payload(
            sources=source_entries,
            blocks=block_entries,
            tests=tests_code,
        )
        
        log_step("subprocess", "Running test in subprocess", {
            "sources": [entry["file_path"] for entry in source_entries],
            "blocks": [block.block_id for block in block_entries],
        })
        
        trace_payload = run_with_block_tracing_subprocess(payload=payload)
        
        log_step("subprocess", "Subprocess completed", {
            'has_error': 'error' in trace_payload,
            'trace_entries_count': len(trace_payload.get('trace', [])),
            'has_source_loading_errors': len(trace_payload.get('source_loading_errors', [])) > 0,
        })
    trace_entries: List[Dict[str, Any]] = trace_payload.get("trace", []) or []
    error_info: Dict[str, Any] | None = trace_payload.get("error")
    source_loading_errors: List[Dict[str, Any]] = trace_payload.get("source_loading_errors", [])
    stderr_text = trace_payload.get("stderr")
    
    print(
        f"[orchestrator] trace_entries count: {len(trace_entries)}, "
        f"error_info: {error_info}",
    )
    
    # Log source loading errors if any
    if source_loading_errors:
        print(f"[orchestrator] WARNING: {len(source_loading_errors)} source file(s) failed to load:", file=sys.stderr)
        for err in source_loading_errors:
            error_type = err.get("error_type", "unknown")
            file_path = err.get("file_path", "unknown")
            message = err.get("message", "Unknown error")
            print(
                f"[orchestrator]   - {file_path}: {error_type} - {message[:150]}",
                file=sys.stderr,
            )
            if error_type == "decorator_framework_error":
                print(
                    f"[orchestrator]     This is likely a framework decorator issue. "
                    f"Stubs were provided but may need additional framework objects.",
                    file=sys.stderr,
                )
    
    if stderr_text:
        print("[orchestrator] runner stderr:\n", stderr_text)

        log_step("block_lookup", "Building block lookup", {
            'blocks_count': len(block_entries),
        })
        
        block_lookup = _build_block_info_lookup(block_entries, source_entries)
        snapshot_pairs = _build_runtime_snapshots_from_trace(trace_entries)
        
        log_step("snapshot_build", f"Built {len(snapshot_pairs)} snapshot pairs", {
            'trace_entries_count': len(trace_entries),
        })

        block_infos: List[BlockInfo] = []
        runtime_states: List[RuntimeStateSnapshot] = []
        for block_id, snapshot in snapshot_pairs:
            block_info = block_lookup.get(block_id)
            if block_info is None:
                continue
            block_infos.append(block_info)
            runtime_states.append(snapshot)

        log_step("block_match", f"Matched {len(block_infos)} blocks with runtime states", {
            'block_infos_count': len(block_infos),
            'runtime_states_count': len(runtime_states),
        })

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
            
            # Test failed before executing any blocks (e.g., syntax error, missing function call, source loading error)
            # Check if we have source loading errors
            if source_loading_errors:
            # Prioritize source loading errors in the description
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
                    f"Files affected: {', '.join(e['file_path'] for e in source_loading_errors)}. "
                    f"Errors: {source_loading_errors[0].get('message', 'Unknown error')}"
                )
                notes = source_loading_errors[0].get("traceback")
        elif error_info:
            actual_description = error_info.get("message", "Test failed before executing any code blocks")
            notes = error_info.get("traceback")
        else:
            actual_description = "Test failed before executing any code blocks"
            notes = None
        
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
        
        fallback_blocks: List[BlockInfo] = [
            block_lookup[block.block_id]
            for block in block_entries
            if block.block_id in block_lookup
        ]

            log_step("no_blocks", "No blocks executed, creating fallback result")
            
            return LlmDebugRunResult(
                suite=suite,
                test_case=test_case,
                trace_payload=trace_payload,
                debug_analysis=debug_analysis,
                blocks=fallback_blocks,
                runtime_states=[],
                execution_log=execution_log,
            )

        log_step("analysis", f"Analyzing {len(block_infos)} blocks", {
            'runtime_states_count': len(runtime_states),
        })
        
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
        
        log_step("complete", "Pipeline completed successfully", {
            'total_time': time.time() - pipeline_start_time,
            'blocks_analyzed': len(block_infos),
        })

        return LlmDebugRunResult(
            suite=suite,
            test_case=test_case,
            trace_payload=trace_payload,
            debug_analysis=debug_analysis,
            blocks=block_infos,
            runtime_states=runtime_states,
            execution_log=execution_log,
        )
    except Exception as e:
        elapsed = time.time() - pipeline_start_time
        tb = traceback.format_exc()
        log_step("error", f"Pipeline failed after {elapsed:.2f}s: {type(e).__name__}: {e}", {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'traceback': tb,
        })
        # Re-raise with enhanced context
        raise


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
    Includes errors, warnings, execution logs, and source loading status.
    """

    trace_entries: List[Dict[str, Any]] = (
        run_result.trace_payload.get("trace", []) or []
    )
    block_lookup: Dict[str, BlockInfo] = {block.id: block for block in run_result.blocks}
    
    # Extract error information from trace payload
    error_info = run_result.trace_payload.get("error")
    source_loading_errors = run_result.trace_payload.get("source_loading_errors", [])
    test_execution_error = run_result.trace_payload.get("test_execution_error")
    
    # Build errors list with stack traces
    errors: List[Dict[str, Any]] = []
    if error_info:
        errors.append({
            "error_type": error_info.get("error_type", "unknown"),
            "message": error_info.get("message", "Unknown error"),
            "traceback": error_info.get("traceback"),
            "context": "test_execution",
        })
    if source_loading_errors:
        for err in source_loading_errors:
            errors.append({
                "error_type": err.get("error_type", "unknown"),
                "message": err.get("message", "Unknown error"),
                "traceback": err.get("traceback"),
                "file_path": err.get("file_path"),
                "context": "source_loading",
            })
    if test_execution_error:
        errors.append({
            "error_type": test_execution_error.get("error_type", "unknown"),
            "message": test_execution_error.get("message", "Unknown error"),
            "traceback": test_execution_error.get("traceback"),
            "context": "test_execution",
        })
    
    # Build warnings list
    warnings: List[Dict[str, Any]] = []
    if source_loading_errors:
        warnings.append({
            "type": "source_loading_failed",
            "message": f"{len(source_loading_errors)} source file(s) failed to load",
            "details": source_loading_errors,
        })
    
    # Build source loading status
    summary = run_result.trace_payload.get("summary", {})
    sources_loaded = summary.get("sources_loaded", 0)
    sources_failed = len(source_loading_errors)
    source_loading_status = {
        "total": sources_loaded + sources_failed,
        "loaded": sources_loaded,
        "failed": sources_failed,
        "errors": source_loading_errors,
    }

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

    payload = {
        "suite": run_result.suite.model_dump(),
        "test_case": run_result.test_case.model_dump(),
        "trace": trace_entries,
        "steps": steps,
        "problems": problems,
        "nodes": nodes,
        "edges": edges,
        "analysis": run_result.debug_analysis.model_dump(),
    }
    
    # Add enhanced error information
    if errors:
        payload["errors"] = errors
    if warnings:
        payload["warnings"] = warnings
    if run_result.execution_log:
        payload["execution_log"] = run_result.execution_log
    payload["source_loading_status"] = source_loading_status
    
    return payload


