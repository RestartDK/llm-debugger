"""
Storage utilities for reading and writing JSON files.
"""
import json
import os
from typing import Any

# Data directory path
DATA_DIR = "data"
PROJECT_CONTEXT_FILE = os.path.join(DATA_DIR, "project_context.json")
CODE_CHUNKS_FILE = os.path.join(DATA_DIR, "code_chunks.json")
CHANGES_HISTORY_FILE = os.path.join(DATA_DIR, "changes_history.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def read_json_file(filepath: str, default: Any = None) -> Any:
    """Read JSON file, return default if file doesn't exist."""
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def write_json_file(filepath: str, data: Any) -> None:
    """Write data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_to_json_file(filepath: str, item: Any) -> None:
    """Append item to a JSON list file."""
    data = read_json_file(filepath, default=[])
    if not isinstance(data, list):
        data = []
    data.append(item)
    write_json_file(filepath, data)

