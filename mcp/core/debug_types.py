"""
Shared dataclasses and serialization helpers for the block tracing prototype.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Tuple

MAX_SERIALIZE_DEPTH = 2
MAX_COLLECTION_ITEMS = 20


@dataclass(frozen=True)
class BasicBlock:
    """
    Minimal BasicBlock representation used by the dummy CFG fixture.
    """

    block_id: str
    file_path: str
    start_line: int
    end_line: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceEntry:
    """
    Captured locals snapshot for a specific CFG block execution.
    """

    block_id: str
    step_index: int
    locals: Dict[str, Any]
    file_path: str
    line_no: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "step_index": self.step_index,
            "file_path": self.file_path,
            "line_no": self.line_no,
            "locals": self.locals,
        }


def serialize_value(value: Any, *, depth: int = 0) -> Any:
    """
    Convert arbitrary Python objects into JSON-safe, size-bounded structures.
    """

    if depth >= MAX_SERIALIZE_DEPTH:
        return repr(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, dict):
        limited_items = list(value.items())[:MAX_COLLECTION_ITEMS]
        return {
            str(k): serialize_value(v, depth=depth + 1) for k, v in limited_items
        }

    if isinstance(value, (list, tuple, set)):
        limited_items = list(value)[:MAX_COLLECTION_ITEMS]
        serialized = [serialize_value(item, depth=depth + 1) for item in limited_items]
        return serialized

    if hasattr(value, "__dict__"):
        return serialize_value(vars(value), depth=depth + 1)

    return repr(value)


def serialize_locals(local_vars: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize locals while filtering out private / noisy entries.
    """

    filtered = {
        name: val for name, val in local_vars.items() if not name.startswith("__")
    }
    return {name: serialize_value(val) for name, val in filtered.items()}


def build_exit_line_lookup(
    blocks: Iterable[BasicBlock],
) -> Dict[Tuple[str, int], str]:
    """
    Build a (file_path, end_line) -> block_id index for quick tracer lookups.
    """

    lookup: Dict[Tuple[str, int], str] = {}
    for block in blocks:
        lookup[(block.file_path, block.end_line)] = block.block_id
    return lookup

