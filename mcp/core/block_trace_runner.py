"""
Standalone runner executed in a subprocess to capture basic-block locals traces.
"""
from __future__ import annotations

import json
import sys
import traceback
import types
from pathlib import Path
from typing import Dict, List
from .debug_types import BasicBlock, TraceEntry, build_exit_line_lookup
from .runtime_tracer import MAX_TRACE_STEPS, make_line_tracer


def _path_to_module_name(file_path: str) -> str:
    without_suffix = Path(file_path).with_suffix("")
    return ".".join(without_suffix.parts)


def _load_sources(sources: List[Dict[str, str]], namespace: Dict[str, object]):
    """
    Execute each source file in its own module namespace and register it.
    """

    for entry in sources:
        file_path = entry["file_path"]
        code = entry["code"]
        module_name = _path_to_module_name(file_path)
        parts = module_name.split(".")
        for idx in range(1, len(parts)):
            pkg_name = ".".join(parts[:idx])
            if pkg_name not in sys.modules:
                pkg_module = types.ModuleType(pkg_name)
                pkg_module.__path__ = []  # type: ignore[attr-defined]
                sys.modules[pkg_name] = pkg_module
        module = types.ModuleType(module_name)
        module.__file__ = file_path
        compiled = compile(code, file_path, "exec")
        exec(compiled, module.__dict__)
        sys.modules[module_name] = module
        if len(parts) > 1:
            parent_name = ".".join(parts[:-1])
            setattr(sys.modules[parent_name], parts[-1], module)
        # Mirror definitions into the shared namespace for tests
        namespace.update(module.__dict__)


def _run_payload(payload: Dict[str, object]) -> Dict[str, object]:
    sources = payload.get("sources") or []
    blocks_raw = payload.get("blocks") or []
    tests_code = payload.get("tests") or ""
    max_steps = payload.get("max_steps")

    # Debug: log basic runner payload structure
    print("[runner] sources:", sources, file=sys.stderr)
    print("[runner] blocks_raw:", blocks_raw, file=sys.stderr)
    print("[runner] tests_code (first 200 chars):", tests_code[:200], file=sys.stderr)

    blocks = [BasicBlock(**block_dict) for block_dict in blocks_raw]
    exit_lookup = build_exit_line_lookup(blocks)
    print("[runner] exit_lookup keys:", list(exit_lookup.keys()), file=sys.stderr)

    # NOTE: We intentionally do NOT restrict tracing to a specific file_filter here.
    # Some environments may report absolute paths or slightly different filenames
    # than the simple `file_path` strings we pass in the payload. If we filtered
    # by `file_path` alone, we could accidentally drop all relevant frames and end
    # up with an empty trace.
    tracer = make_line_tracer(
        exit_lookup,
        max_steps=max_steps or MAX_TRACE_STEPS,
        file_filter=None,
    )
    namespace: Dict[str, object] = {"__name__": "__main__"}
    _load_sources(sources, namespace)

    def _execute():
        if tests_code:
            compiled_tests = compile(
                tests_code, payload.get("tests_filename", "debug_session/tests.py"), "exec"
            )
            exec(compiled_tests, namespace)

    sys.settrace(tracer)
    error: Dict[str, object] | None = None
    try:
        _execute()
    except Exception as exc:  # pylint: disable=broad-except
        tb = traceback.format_exc()
        error = {"message": str(exc), "traceback": tb}
    finally:
        sys.settrace(None)

    trace_entries: List[TraceEntry] = getattr(
        tracer, "_ldb_trace_entries", []  # type: ignore[attr-defined]
    )
    debug_meta: Dict[str, object] = getattr(
        tracer, "_ldb_debug_meta", {}  # type: ignore[attr-defined]
    )
    print(
        f"[runner] captured {len(trace_entries)} trace entries",
        file=sys.stderr,
    )
    total_events = debug_meta.get("total_events")
    unmatched_samples = debug_meta.get("unmatched_samples") or []
    print(
        f"[runner] total line events seen: {total_events}",
        file=sys.stderr,
    )
    if unmatched_samples:
        print(
            "[runner] first unmatched (filename, line_no) samples:",
            unmatched_samples,
            file=sys.stderr,
        )
    if trace_entries:
        first = trace_entries[0]
        print(
            "[runner] first trace entry:",
            {
                "block_id": first.block_id,
                "file_path": first.file_path,
                "line_no": first.line_no,
                "locals": first.locals,
            },
            file=sys.stderr,
        )

    result: Dict[str, object] = {
        "ok": error is None,
        "trace": [entry.to_dict() for entry in trace_entries],
        "error": error,
    }
    return result


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"message": f"Invalid JSON payload: {exc}"}}
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    response = _run_payload(payload)
    print(json.dumps(response))


if __name__ == "__main__":
    main()

