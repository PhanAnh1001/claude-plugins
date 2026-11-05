"""Atomic handoff ledger written by `term` and consumed by `paseo`."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .constants import HANDOFF_FILENAME, HANDOFF_SUBDIR
from .paths import state_dir


@dataclass(frozen=True)
class Handoff:
    session_id: str
    agent_id: str
    at: float


def ledger_path() -> Path:
    return state_dir() / HANDOFF_SUBDIR / HANDOFF_FILENAME


def _key(root: Path) -> str:
    try:
        return str(root.resolve())
    except (OSError, RuntimeError):
        return str(root)


def _read_entries() -> Dict[str, dict]:
    try:
        data = json.loads(ledger_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _warn(message: str) -> None:
    print(f"cc-switch: {message}", file=sys.stderr)


def _write_entries(entries: Dict[str, dict]) -> None:
    path = ledger_path()
    temp_name = ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=str(path.parent))
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(entries, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = ""
    except OSError as exc:
        _warn(f"không ghi được sổ bàn giao {path}: {exc}")
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def record(root: Path, session_id: str, agent_id: str) -> None:
    entries = _read_entries()
    entries[_key(root)] = {
        "session_id": session_id,
        "agent_id": agent_id,
        "at": int(time.time()),
    }
    _write_entries(entries)


def lookup(root: Path) -> Optional[Handoff]:
    entry = _read_entries().get(_key(root))
    if not isinstance(entry, dict):
        return None
    session_id = entry.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    agent_id = entry.get("agent_id")
    at = entry.get("at")
    return Handoff(
        session_id=session_id,
        agent_id=agent_id if isinstance(agent_id, str) else "",
        at=float(at) if isinstance(at, (int, float)) else 0.0,
    )


def forget(root: Path, session_id: Optional[str] = None) -> None:
    """Drop the project entry, or only when it still points at `session_id`."""
    entries = _read_entries()
    key = _key(root)
    entry = entries.get(key)
    if not isinstance(entry, dict):
        return
    if session_id is not None and entry.get("session_id") != session_id:
        return
    entries.pop(key, None)
    _write_entries(entries)
