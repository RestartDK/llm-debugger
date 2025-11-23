"""
Helpers for tracing Python execution and capturing CFG-aware locals snapshots.
"""
from __future__ import annotations

import sys
from types import FrameType
from typing import Dict, Iterable, List, Optional, Tuple

from .debug_types import TraceEntry, serialize_locals

MAX_TRACE_STEPS = 2000


def make_line_tracer(
    exit_line_lookup: Dict[Tuple[str, int], str],
    *,
    max_steps: int = MAX_TRACE_STEPS,
    file_filter: Optional[Iterable[str]] = None,
):
    """
    Build a sys.settrace-compatible function that records TraceEntry objects.
    """

    allowed_files = set(file_filter) if file_filter else None
    trace_entries: List[TraceEntry] = []
    step_counter = {"value": 0}
    # Debug metadata so callers can understand why a trace might be empty.
    # - total_events: how many "line" events we actually saw.
    # - unmatched_samples: a few (filename, line_no) pairs that did NOT map
    #   to any configured BasicBlock end_line.
    debug_meta: Dict[str, object] = {
        "total_events": 0,
        "unmatched_samples": [],  # type: ignore[assignment]
    }
    unmatched_samples: List[Tuple[str, int]] = []
    
    # Log tracer initialization
    lookup_size = len(exit_line_lookup)
    print(
        f"[runtime_tracer] Creating line tracer: lookup_size={lookup_size}, "
        f"max_steps={max_steps}, file_filter={'enabled' if allowed_files else 'disabled'}",
        file=sys.stderr,
    )
    if lookup_size > 0:
        sample_keys = list(exit_line_lookup.keys())[:5]
        print(
            f"[runtime_tracer] Sample lookup keys: {sample_keys}",
            file=sys.stderr,
        )

    def tracer(frame: FrameType, event: str, arg):
        if event != "line":
            return tracer

        filename = frame.f_code.co_filename
        if allowed_files is not None and filename not in allowed_files:
            return tracer

        # Count every line event so we can distinguish "no tracing at all"
        # from "tracing happened but no lines matched our blocks".
        debug_meta["total_events"] = int(debug_meta["total_events"]) + 1  # type: ignore[call-overload]
        
        # Log first few events for debugging
        total_events = int(debug_meta["total_events"])
        if total_events <= 5:
            print(
                f"[runtime_tracer] Event #{total_events}: {filename}:{frame.f_lineno} "
                f"(function={frame.f_code.co_name})",
                file=sys.stderr,
            )

        key = (filename, frame.f_lineno)
        block_id = exit_line_lookup.get(key)

        if block_id and step_counter["value"] < max_steps:
            step_idx = step_counter["value"]
            trace_entries.append(
                TraceEntry(
                    block_id=block_id,
                    step_index=step_idx,
                    locals=serialize_locals(frame.f_locals),
                    file_path=filename,
                    line_no=frame.f_lineno,
                )
            )
            # Log when we capture a trace entry
            if step_idx < 5 or step_idx % 50 == 0:
                locals_count = len(frame.f_locals)
                print(
                    f"[runtime_tracer] Captured trace entry #{step_idx}: "
                    f"block_id={block_id}, file={filename}:{frame.f_lineno}, "
                    f"locals_count={locals_count}",
                    file=sys.stderr,
                )
            step_counter["value"] += 1
        else:
            # Collect a small sample of unmatched events for debugging.
            if len(unmatched_samples) < 10:
                unmatched_samples.append((filename, frame.f_lineno))
                if len(unmatched_samples) <= 3:
                    print(
                        f"[runtime_tracer] Unmatched event: {filename}:{frame.f_lineno} "
                        f"(not in exit_line_lookup)",
                        file=sys.stderr,
                    )
        
        # Log if we're approaching max_steps
        if step_counter["value"] >= max_steps:
            if step_counter["value"] == max_steps:
                print(
                    f"[runtime_tracer] WARNING: Reached max_steps limit ({max_steps}), "
                    f"stopping trace capture",
                    file=sys.stderr,
                )

        return tracer

    # Attach debug metadata so the runner can introspect traces when things go wrong.
    debug_meta["unmatched_samples"] = unmatched_samples
    tracer._ldb_trace_entries = trace_entries  # type: ignore[attr-defined]
    tracer._ldb_debug_meta = debug_meta  # type: ignore[attr-defined]
    
    print(
        f"[runtime_tracer] Tracer created: will capture up to {max_steps} trace entries",
        file=sys.stderr,
    )
    
    return tracer


def run_with_tracer(func, tracer):
    """
    Convenience helper to install/uninstall the tracer around a callable.
    """

    print("[runtime_tracer] Installing tracer...", file=sys.stderr)
    prev_tracer = sys.gettrace()
    sys.settrace(tracer)
    try:
        print("[runtime_tracer] Executing function with tracer active...", file=sys.stderr)
        func()
        print("[runtime_tracer] Function execution completed", file=sys.stderr)
    finally:
        sys.settrace(prev_tracer)
        print("[runtime_tracer] Tracer uninstalled", file=sys.stderr)

