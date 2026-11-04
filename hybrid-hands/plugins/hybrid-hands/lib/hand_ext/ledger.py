"""Run ledger (JSON list): tokens and quota per attempt, never USD."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .locked_json import locked, read_json, write_atomic


def append_entry(path: Path, entry: Dict[str, Any]) -> None:
    with locked(path):
        entries = read_json(path, [])
        entries.append(entry)
        write_atomic(path, entries)


def read_entries(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    with locked(path):
        return read_json(path, [])
