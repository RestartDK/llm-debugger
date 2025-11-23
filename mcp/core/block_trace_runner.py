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


def _load_sources(sources: List[Dict[str, str]], namespace: Dict[str, object]) -> List[Dict[str, str]]:
    """
    Execute each source file in its own module namespace and register it.
    
    Returns:
        List of error dictionaries for any files that failed to load, empty if all succeeded.
        Each error dict contains: {"file_path": str, "error_type": str, "message": str, "traceback": str}
    """
    errors = []

    for entry in sources:
        file_path = entry["file_path"]
        code = entry["code"]
        module_name = _path_to_module_name(file_path)
        
        print(f"[runner] Loading source file: {file_path}", file=sys.stderr)
        print(f"[runner] Available stubs in namespace: {[k for k in namespace.keys() if not k.startswith('__')]}", file=sys.stderr)
        
        try:
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
            
            # Execute with error handling
            try:
        exec(compiled, module.__dict__)
                print(f"[runner] Successfully loaded source file: {file_path}", file=sys.stderr)
            except NameError as e:
                # Check if it's a decorator-related error
                error_msg = str(e)
                if any(framework_obj in error_msg for framework_obj in ["app", "Depends", "Request", "Flask", "Blueprint", "django", "Django"]):
                    error_type = "decorator_framework_error"
                    suggestion = (
                        f"Framework decorator error detected. The code uses framework objects "
                        f"({error_msg.split('name ')[-1] if 'name ' in error_msg else 'unknown'}) "
                        f"that may need additional stubs. Current stubs: {list(namespace.keys())}"
                    )
                else:
                    error_type = "name_error"
                    suggestion = f"NameError: {error_msg}. Check imports and variable definitions."
                
                tb = traceback.format_exc()
                errors.append({
                    "file_path": file_path,
                    "error_type": error_type,
                    "message": f"{error_msg}. {suggestion}",
                    "traceback": tb,
                })
                print(f"[runner] ERROR loading {file_path}: {error_type} - {error_msg}", file=sys.stderr)
                print(f"[runner] Traceback:\n{tb}", file=sys.stderr)
                # Continue with other files even if one fails
                continue
            except SyntaxError as e:
                error_type = "syntax_error"
                errors.append({
                    "file_path": file_path,
                    "error_type": error_type,
                    "message": f"Syntax error at line {e.lineno}: {e.msg}",
                    "traceback": traceback.format_exc(),
                })
                print(f"[runner] ERROR loading {file_path}: Syntax error at line {e.lineno}: {e.msg}", file=sys.stderr)
                continue
            except ImportError as e:
                error_type = "import_error"
                errors.append({
                    "file_path": file_path,
                    "error_type": error_type,
                    "message": f"Import error: {e.msg if hasattr(e, 'msg') else str(e)}",
                    "traceback": traceback.format_exc(),
                })
                print(f"[runner] ERROR loading {file_path}: Import error - {e}", file=sys.stderr)
                continue
            except Exception as e:
                error_type = "execution_error"
                errors.append({
                    "file_path": file_path,
                    "error_type": error_type,
                    "message": f"Error executing source code: {str(e)}",
                    "traceback": traceback.format_exc(),
                })
                print(f"[runner] ERROR loading {file_path}: Execution error - {type(e).__name__}: {e}", file=sys.stderr)
                print(f"[runner] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
                continue
            
        sys.modules[module_name] = module
        if len(parts) > 1:
            parent_name = ".".join(parts[:-1])
            setattr(sys.modules[parent_name], parts[-1], module)
        # Mirror definitions into the shared namespace for tests
        namespace.update(module.__dict__)
            
        except Exception as e:
            # Catch-all for any other errors during module setup
            error_type = "module_setup_error"
            errors.append({
                "file_path": file_path,
                "error_type": error_type,
                "message": f"Error setting up module: {str(e)}",
                "traceback": traceback.format_exc(),
            })
            print(f"[runner] ERROR setting up module for {file_path}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
    
    if errors:
        print(f"[runner] Failed to load {len(errors)}/{len(sources)} source file(s)", file=sys.stderr)
    else:
        print(f"[runner] Successfully loaded all {len(sources)} source file(s)", file=sys.stderr)
    
    return errors


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
    
    # Provide stub implementations for common framework dependencies
    # to prevent NameError when executing source code with decorators
    class StubApp:
        """Stub FastAPI app object for decorators"""
        def post(self, path: str, *args, **kwargs):
            def decorator(func):
                return func  # Return function unchanged
            return decorator
        
        def get(self, path: str, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def put(self, path: str, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def delete(self, path: str, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    class StubDepends:
        """Stub FastAPI Depends for dependency injection"""
        def __init__(self, func=None, *args, **kwargs):
            self.func = func
    
    class StubRequest:
        """Stub FastAPI Request object"""
        pass
    
    class StubFlaskApp:
        """Stub Flask app class/object for decorators"""
        def __init__(self, *args, **kwargs):
            # Allow Flask(__name__) instantiation
            pass
        
        def route(self, path: str, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def __call__(self, *args, **kwargs):
            # Allow app to be callable
            return self
    
    class StubBlueprint:
        """Stub Flask Blueprint object"""
        def route(self, path: str, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    # Add stubs to namespace before loading sources
    # Log what stubs we're providing to help debug decorator-related errors
    print("[runner] Providing framework stubs for decorator support:", file=sys.stderr)
    stubs_provided = []
    
    namespace["app"] = StubApp()
    stubs_provided.append("app (FastAPI)")
    print("  - app: FastAPI application stub (supports @app.post, @app.get, etc.)", file=sys.stderr)
    
    namespace["Depends"] = StubDepends
    stubs_provided.append("Depends (FastAPI)")
    print("  - Depends: FastAPI dependency injection stub", file=sys.stderr)
    
    namespace["Request"] = StubRequest
    stubs_provided.append("Request (FastAPI)")
    print("  - Request: FastAPI Request object stub", file=sys.stderr)
    
    # Flask stubs
    namespace["Flask"] = StubFlaskApp
    stubs_provided.append("Flask")
    print("  - Flask: Flask application stub (supports @app.route)", file=sys.stderr)
    
    namespace["Blueprint"] = StubBlueprint
    stubs_provided.append("Blueprint (Flask)")
    print("  - Blueprint: Flask Blueprint stub", file=sys.stderr)
    
    # Also add common imports that might be missing
    # sys is always available (it's imported at module level)
    namespace["sys"] = sys
    stubs_provided.append("sys (stdlib)")
    print("  - sys: Standard library module (always available)", file=sys.stderr)
    
    try:
        import os
        namespace["os"] = os
        stubs_provided.append("os (stdlib)")
        print("  - os: Standard library module", file=sys.stderr)
    except ImportError:
        print("  - os: Not available", file=sys.stderr)
    
    try:
        import requests
        namespace["requests"] = requests
        stubs_provided.append("requests (library)")
        print("  - requests: HTTP library module", file=sys.stderr)
    except ImportError:
        print("  - requests: Not available (may cause ImportError in source code)", file=sys.stderr)
    
    print(f"[runner] Total stubs/modules provided: {len(stubs_provided)}", file=sys.stderr)
    
    # Load sources with error handling
    source_loading_errors = _load_sources(sources, namespace)
    
    # If we had source loading errors, add them to the result
    if source_loading_errors:
        print(f"[runner] WARNING: {len(source_loading_errors)} source file(s) failed to load:", file=sys.stderr)
        for err in source_loading_errors:
            print(f"  - {err['file_path']}: {err['error_type']} - {err['message'][:100]}", file=sys.stderr)

    def _execute():
        if tests_code:
            print(f"[runner] Compiling test code ({len(tests_code)} chars)...", file=sys.stderr)
            compiled_tests = compile(
                tests_code, payload.get("tests_filename", "debug_session/tests.py"), "exec"
            )
            print("[runner] Executing compiled test code...", file=sys.stderr)
            exec(compiled_tests, namespace)
            print("[runner] Test code execution finished", file=sys.stderr)
        else:
            print("[runner] WARNING: No test code provided to execute", file=sys.stderr)

    print("[runner] Installing tracer before test execution...", file=sys.stderr)
    sys.settrace(tracer)
    error: Dict[str, object] | None = None
    test_execution_error: Dict[str, object] | None = None
    
    try:
        print("[runner] Starting test execution with tracer active...", file=sys.stderr)
        _execute()
        print("[runner] Test execution completed successfully", file=sys.stderr)
    except AssertionError as exc:
        # Test assertion failure - this is expected for failed tests
        tb = traceback.format_exc()
        test_execution_error = {
            "error_type": "assertion_failure",
            "message": f"Test assertion failed: {str(exc)}",
            "traceback": tb,
        }
        print(f"[runner] Test assertion failed (expected for test failures): {exc}", file=sys.stderr)
        # Don't set error - assertion failures are normal test outcomes
    except NameError as exc:
        # Missing name during test execution
        tb = traceback.format_exc()
        error = {
            "error_type": "test_name_error",
            "message": f"NameError during test execution: {str(exc)}. Check that test code references correct function/variable names.",
            "traceback": tb,
        }
        print(f"[runner] ERROR during test execution - NameError: {exc}", file=sys.stderr)
        print(f"[runner] Traceback:\n{tb}", file=sys.stderr)
    except SyntaxError as exc:
        # Syntax error in test code
        tb = traceback.format_exc()
        error = {
            "error_type": "test_syntax_error",
            "message": f"Syntax error in test code at line {exc.lineno}: {exc.msg}",
            "traceback": tb,
        }
        print(f"[runner] ERROR during test execution - Syntax error at line {exc.lineno}: {exc.msg}", file=sys.stderr)
    except Exception as exc:  # pylint: disable=broad-except
        # Other runtime errors during test execution
        tb = traceback.format_exc()
        error = {
            "error_type": "test_execution_error",
            "message": f"Error during test execution: {type(exc).__name__}: {str(exc)}",
            "traceback": tb,
        }
        print(f"[runner] ERROR during test execution - {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"[runner] Traceback:\n{tb}", file=sys.stderr)
    finally:
        print("[runner] Uninstalling tracer...", file=sys.stderr)
        sys.settrace(None)

    trace_entries: List[TraceEntry] = getattr(
        tracer, "_ldb_trace_entries", []  # type: ignore[attr-defined]
    )
    debug_meta: Dict[str, object] = getattr(
        tracer, "_ldb_debug_meta", {}  # type: ignore[attr-defined]
    )
    print(
        f"[runner] Tracer captured {len(trace_entries)} trace entries",
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

    # Build result with error categorization
    result: Dict[str, object] = {
        "ok": error is None and len(source_loading_errors) == 0,
        "trace": [entry.to_dict() for entry in trace_entries],
        "error": error,
    }
    
    # Add source loading errors if any
    if source_loading_errors:
        result["source_loading_errors"] = source_loading_errors
        result["source_loading_failed"] = True
        print(f"[runner] Result includes {len(source_loading_errors)} source loading error(s)", file=sys.stderr)
    else:
        result["source_loading_failed"] = False
    
    # Add test execution error if it was an assertion failure (not a critical error)
    if test_execution_error:
        result["test_execution_error"] = test_execution_error
        print(f"[runner] Result includes test execution error (type: {test_execution_error['error_type']})", file=sys.stderr)
    
    # Add summary information
    result["summary"] = {
        "sources_loaded": len(sources) - len(source_loading_errors),
        "sources_failed": len(source_loading_errors),
        "trace_entries": len(trace_entries),
        "has_error": error is not None,
        "has_source_loading_errors": len(source_loading_errors) > 0,
    }
    
    print(f"[runner] Execution summary: {result['summary']}", file=sys.stderr)
    
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

