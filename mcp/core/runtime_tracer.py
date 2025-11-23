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

    def tracer(frame: FrameType, event: str, arg):
        if event != "line":
            return tracer

        filename = frame.f_code.co_filename
        if allowed_files is not None and filename not in allowed_files:
            return tracer

        # Count every line event so we can distinguish "no tracing at all"
        # from "tracing happened but no lines matched our blocks".
        debug_meta["total_events"] = int(debug_meta["total_events"]) + 1  # type: ignore[call-overload]

        key = (filename, frame.f_lineno)
        block_id = exit_line_lookup.get(key)

        if block_id and step_counter["value"] < max_steps:
            trace_entries.append(
                TraceEntry(
                    block_id=block_id,
                    step_index=step_counter["value"],
                    locals=serialize_locals(frame.f_locals),
                    file_path=filename,
                    line_no=frame.f_lineno,
                )
            )
            step_counter["value"] += 1
        else:
            # Collect a small sample of unmatched events for debugging.
            if len(unmatched_samples) < 10:
                unmatched_samples.append((filename, frame.f_lineno))

        return tracer

    # Attach debug metadata so the runner can introspect traces when things go wrong.
    debug_meta["unmatched_samples"] = unmatched_samples
    tracer._ldb_trace_entries = trace_entries  # type: ignore[attr-defined]
    tracer._ldb_debug_meta = debug_meta  # type: ignore[attr-defined]
    return tracer


def run_with_tracer(func, tracer):
    """
    Convenience helper to install/uninstall the tracer around a callable.
    """

    prev_tracer = sys.gettrace()
    sys.settrace(tracer)
    try:
        func()
    finally:
        sys.settrace(prev_tracer)

