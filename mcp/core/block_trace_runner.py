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

    blocks = [BasicBlock(**block_dict) for block_dict in blocks_raw]
    exit_lookup = build_exit_line_lookup(blocks)
    file_filter = {entry["file_path"] for entry in sources}

    tracer = make_line_tracer(
        exit_lookup,
        max_steps=max_steps or MAX_TRACE_STEPS,
        file_filter=file_filter,
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

