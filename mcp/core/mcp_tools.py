"""
MCP tool functions for the debug context server.
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Dict, List, Optional
from .debug_types import BasicBlock
from .dummy_cfg import get_dummy_blocks, get_dummy_sources
from .storage import save_code_context

RUNNER_MODULE = "core.block_trace_runner"
DEMO_TESTS = """
# Complex e-commerce order processing test
from ecommerce.processor import process_order

order_data = {
    'items': [
        {'name': 'Laptop', 'price': 999.99, 'quantity': 1},
        {'name': 'Mouse', 'price': 29.99, 'quantity': 2},
        {'name': 'Keyboard', 'price': 79.99, 'quantity': 1},
        {'name': 'Monitor', 'price': 299.99, 'quantity': 0}  # Zero quantity test
    ],
    'user_tier': 'premium',
    'coupon_code': 'SAVE20',
    'shipping_state': 'CA',
    'tax_exempt': False
}

result = process_order(order_data)
final_total = result['order_summary']['final_total']
assert final_total > 0
assert result['order_summary']['item_count'] == 4
assert result['discounts']['discount'] > 0
"""


def submit_code_context(text: str) -> str:
    """
    Submit code context as raw text.

    Args:
        text: Raw text containing code chunks, explanations, and relationships

    Returns:
        Success message with filename
    """

    return save_code_context(text)


def build_runner_payload(
    *,
    sources: Optional[List[Dict[str, str]]] = None,
    blocks: Optional[List[BasicBlock]] = None,
    tests: str = "",
    max_steps: Optional[int] = None,
) -> Dict[str, object]:
    """
    Prepare the JSON payload understood by the tracing subprocess.
    """

    source_entries = sources or get_dummy_sources()
    block_entries = blocks or get_dummy_blocks()
    payload = {
        "sources": source_entries,
        "blocks": [block.to_dict() for block in block_entries],
        "tests": tests,
    }
    if max_steps is not None:
        payload["max_steps"] = max_steps
    return payload


def run_with_block_tracing_subprocess(
    payload: Optional[Dict[str, object]] = None,
    timeout: float = 5.0,
) -> Dict[str, object]:
    """
    Execute the tracing runner as a subprocess and return its JSON response.
    """

    payload = payload or build_runner_payload(tests=DEMO_TESTS)
    
    # Log payload summary before subprocess execution
    sources_count = len(payload.get("sources", []))
    blocks_count = len(payload.get("blocks", []))
    tests_preview = str(payload.get("tests", ""))[:200]
    print(
        f"[mcp_tools] Starting block tracing subprocess:",
        f"sources={sources_count}, blocks={blocks_count}, "
        f"tests_preview={tests_preview}...",
        file=sys.stderr,
    )
    
    encoded = json.dumps(payload)
    print(f"[mcp_tools] Subprocess payload size: {len(encoded)} bytes", file=sys.stderr)
    
    print(f"[mcp_tools] Executing subprocess: {sys.executable} -m {RUNNER_MODULE}", file=sys.stderr)
    process = subprocess.run(
        [sys.executable, "-m", RUNNER_MODULE],
        input=encoded,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    print(
        f"[mcp_tools] Subprocess completed: returncode={process.returncode}, "
        f"stdout_len={len(process.stdout)}, stderr_len={len(process.stderr or '')}",
        file=sys.stderr,
    )

    stdout = process.stdout.strip()
    try:
        response = json.loads(stdout or "{}")
    except json.JSONDecodeError as e:
        print(
            f"[mcp_tools] ERROR: Failed to parse subprocess JSON response: {e}",
            file=sys.stderr,
        )
        print(f"[mcp_tools] Raw stdout: {stdout[:500]}", file=sys.stderr)
        response = {"ok": False, "error": {"message": f"Failed to parse subprocess response: {e}"}}
    
    response["returncode"] = process.returncode
    if process.stderr:
        response["stderr"] = process.stderr
        print(f"[mcp_tools] Subprocess stderr captured ({len(process.stderr)} chars)", file=sys.stderr)
    
    # Log response summary
    trace_count = len(response.get("trace", []))
    has_error = response.get("error") is not None
    has_source_errors = response.get("source_loading_errors", [])
    print(
        f"[mcp_tools] Subprocess response summary: trace_entries={trace_count}, "
        f"has_error={has_error}, source_loading_errors={len(has_source_errors)}",
        file=sys.stderr,
    )
    
    return response


def print_demo_trace():
    """
    Run the dummy tracing scenario locally and pretty-print the trace.
    """

    result = run_with_block_tracing_subprocess()
    trace = result.get("trace", [])
    print(f"Runner return code: {result.get('returncode')}")
    if not result.get("ok"):
        print("Runner reported an error:", result.get("error"))
    print("Captured Trace Entries:")
    for entry in trace:
        print(
            f"  Step {entry['step_index']:02d} | {entry['block_id']} "
            f"({entry['file_path']}:{entry['line_no']})"
        )
        for name, value in entry["locals"].items():
            print(f"    {name} = {value}")


if __name__ == "__main__":
    print_demo_trace()

