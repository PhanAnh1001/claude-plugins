"""Machine-wide registry of `hand-ext run` attempts: one JSON file per run.

The file lives under `<HYBRID_HANDS_STATE_DIR>/runs/<run_id>.json` (default
`~/.hybrid-hands/runs/`) so `hh-ps` can show a run while it is still in flight, including the
Claude session that invoked it. Writes are atomic and best-effort: a logging failure warns and
never breaks the run. Finished entries older than seven days are pruned on the next write.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from hh_store import bump_revision

from .backends.base import Usage
from .constants import (
    HAND_RUN_STATUS_RUNNING, HAND_RUNS_RETENTION_SECONDS, HAND_RUNS_UPDATE_SECONDS,
    PARENT_CLAUDE_PID_ENV, PARENT_SESSION_ENV, RUN_REGISTRY_WARNING,
)
from .locked_json import write_atomic

TokenMap = Dict[str, int]


def _iso(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def _token_map(usage: Optional[Union[Usage, Dict[str, Any]]]) -> TokenMap:
    if usage is None:
        return {"input": 0, "cached_input": 0, "output": 0}
    get = usage.get if isinstance(usage, dict) else lambda key, default=0: getattr(
        usage, key, default)
    return {key: max(0, int(get(key, 0) or 0))
            for key in ("input", "cached_input", "output")}


def _int_or_none(raw: Any) -> Optional[int]:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _epoch(raw: Any) -> Optional[float]:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw or "").strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.timestamp()


REGISTRY_ISOLATION_KEYS = ("base_commit", "worktree")


def _worktree_alive(data: Dict[str, Any]) -> bool:
    """A registry outliving retention is still GC ownership proof for its worktree."""
    worktree = data.get("worktree")
    return isinstance(worktree, str) and Path(worktree).is_absolute() and Path(worktree).exists()


class RunRegistry:
    """Best-effort state file for one backend attempt."""

    def __init__(self, runs_dir: Path, run_id: str, label: str, backend: str, model: str,
                 cwd: Path, run_dir: Path, parent_session: Optional[str] = None,
                 parent_claude_pid: Optional[int] = None, pid: Optional[int] = None,
                 clock: Callable[[], float] = time.time, effort: str = "",
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        self.runs_dir = Path(runs_dir)
        self.path = self.runs_dir / f"{run_id}.json"
        self.clock = clock
        self.meta_path = Path(run_dir) / "meta.json" if metadata is not None else None
        self.metadata = dict(metadata or {})
        self.started_at = self.clock()
        self._last_write = 0.0
        self._tokens: TokenMap = _token_map(None)
        self._data: Dict[str, Any] = {
            "run_id": run_id,
            "label": label,
            "backend": backend,
            "model": model,
            "effort": effort,
            "started_at": self.started_at,
            "ended": None,
            "ended_at": None,
            "exit_code": None,
            "cwd": str(cwd),
            "run_dir": str(run_dir),
            "pid": os.getpid() if pid is None else pid,
            "child_pid": None,
            "parent_session": (os.environ.get("CODEX_THREAD_ID") or
                                os.environ.get(PARENT_SESSION_ENV) or None
                               if parent_session is None else parent_session),
            "parent_claude_pid": (_int_or_none(os.environ.get(PARENT_CLAUDE_PID_ENV))
                                  if parent_claude_pid is None else parent_claude_pid),
            "started": _iso(self.started_at),
            "updated_at": int(self.clock()),
            "status": HAND_RUN_STATUS_RUNNING,
            "tokens": dict(self._tokens),
        }
        # GC needs these in the machine registry: base_commit proves a detached HEAD
        # did not move; worktree keeps the entry alive while the checkout exists.
        for key in REGISTRY_ISOLATION_KEYS:
            if self.metadata.get(key):
                self._data[key] = self.metadata[key]

    def start(self) -> None:
        self._write()
        self._cleanup()

    def child(self, child_pid: Optional[int]) -> None:
        """Record the backend CLI pid once, as soon as it is spawned."""
        if child_pid is None or self._data.get("child_pid") == child_pid:
            return
        self._data["child_pid"] = int(child_pid)
        self._write()

    def tick(self, usage: Optional[Union[Usage, Dict[str, Any]]]) -> bool:
        """Refresh tokens at most once per interval; return whether the file was written."""
        now = self.clock()
        if now - self._last_write < HAND_RUNS_UPDATE_SECONDS:
            return False
        self._tokens = _token_map(usage)
        self._data["tokens"] = dict(self._tokens)
        self._data["updated_at"] = int(now)
        return self._write()

    def finish(self, status: Any, exit_code: Optional[int],
               usage: Optional[Union[Usage, Dict[str, Any]]]) -> None:
        now = self.clock()
        self._tokens = _token_map(usage)
        value = getattr(status, "value", status)
        self._data.update({
            "status": str(value),
            "ended": _iso(now),
            "ended_at": now,
            "duration_seconds": max(0.0, now - self.started_at),
            "exit_code": exit_code,
            "updated_at": int(now),
            "tokens": dict(self._tokens),
            "exit": exit_code,
        })
        self._write()
        self._cleanup()

    # ---- writing --------------------------------------------------------
    def _write(self) -> bool:
        targets = [(self.path, self._data)]
        if self.meta_path is not None:
            targets.append((self.meta_path, {**self.metadata, **self._data}))
        success = True
        for path, data in targets:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                write_atomic(path, data)
            except OSError as exc:
                print(f"{RUN_REGISTRY_WARNING}: {exc}", file=sys.stderr)
                success = False
        if success:
            bump_revision()  # signal hh-ps/pane that run state changed; never raises
        self._last_write = self.clock()
        return success

    def _cleanup(self, now: Optional[float] = None) -> None:
        """Delete finished entries older than the retention window, never running ones."""
        moment = self.clock() if now is None else now
        cutoff = moment - HAND_RUNS_RETENTION_SECONDS
        try:
            paths = list(self.runs_dir.glob("*.json"))
        except OSError:
            return
        for path in paths:
            if path == self.path:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("status") == HAND_RUN_STATUS_RUNNING:
                    continue
                if _worktree_alive(data):
                    continue
                ended = _epoch(data.get("ended")) or _epoch(data.get("updated_at"))
                if ended is None:
                    ended = path.stat().st_mtime
                if ended < cutoff:
                    path.unlink()
            except (OSError, ValueError):
                continue
