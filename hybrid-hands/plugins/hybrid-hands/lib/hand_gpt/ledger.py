"""JSON-list spend ledger, locked with fcntl on a sibling .lock file, written atomically."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List

LOCK_SUFFIX = ".lock"


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + LOCK_SUFFIX)
    with open(lock_path, "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"{path}: ledger must be a JSON list")
    return data


def _write_atomic(path: Path, entries: List[Dict[str, Any]]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(entries, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def append_entry(path: Path, entry: Dict[str, Any]) -> None:
    with _locked(path):
        entries = _read(path)
        entries.append(entry)
        _write_atomic(path, entries)


def read_entries(path: Path) -> List[Dict[str, Any]]:
    with _locked(path):
        return _read(path)


def total_usd(path: Path) -> float:
    if not path.is_file():
        return 0.0
    return sum(float(e.get("usd", 0) or 0) for e in read_entries(path))


def check_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _locked(path):
            return os.access(str(path.parent), os.W_OK)
    except OSError:
        return False
