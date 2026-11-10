"""hh-indexer: singleton daemon that keeps the store fresh between reader runs.

It has no parser of its own: every cycle calls the phase-1 ingest functions
(codex_ingest.sync with hh-ps' classifier, claude_ingest.sync), so the
rows equal what hh-ps would write itself. The ingest lock is held only per cycle.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import resource
import select
import signal
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from . import paths, runtime

CODEX_HOME_NAME = ".codex-hand"
CODEX_DIRS = ("sessions", "archived_sessions")
JSONL_SUFFIX = ".jsonl"
ROLLOUT_PREFIX = "rollout-"
CLAUDE_PROJECTS = "projects"
CLAUDE_SESSIONS = "sessions"
SUBAGENTS_DIR = "subagents"
SCOPE_TRANSCRIPT = "claude_transcript"
SCOPE_SUBAGENT = "claude_subagent"

IDLE_TIMEOUT_S = 600.0  # contract: exit when no reader touched last_read for 10 min
DEBOUNCE_S = 0.3
FULL_SCAN_S = 30.0  # sweep of active files + day dirs: lost events, new day dir after midnight
ROLLOUT_SCAN_S = 300.0  # full _machine_rollouts listing (stats every rollout): start + every 5 min
ACTIVE_POLL_S = 2.0  # no-kqueue fallback cadence for recently active files
ACTIVE_WINDOW_S = 600.0  # a JSONL written within 10 min counts as active
MAX_WATCH_FDS = 256
KQ_BATCH = 64
VNODE_FLAGS = ("NOTE_WRITE", "NOTE_EXTEND", "NOTE_RENAME", "NOTE_DELETE")


@dataclass
class Config:
    idle_timeout: float = IDLE_TIMEOUT_S
    debounce: float = DEBOUNCE_S
    full_scan: float = FULL_SCAN_S
    rollout_scan: float = ROLLOUT_SCAN_S
    active_poll: float = ACTIVE_POLL_S


class _Stop(Exception):
    """Raised from the signal handler to unwind the loop cleanly."""


# ---------------------------------------------------------------- sources

def codex_home() -> Path:
    return Path.home() / CODEX_HOME_NAME


def claude_homes() -> List[Path]:
    try:
        from .claude_ingest import account_homes
        return list(account_homes().values())
    except Exception:  # noqa: BLE001 - missing/broken config: index Codex only
        return []


def _recent(path: Path, now: float) -> bool:
    try:
        return now - path.stat().st_mtime <= ACTIVE_WINDOW_S
    except OSError:
        return False


def _claude_files(home: Path, now: float) -> List[Path]:
    root = home / CLAUDE_PROJECTS
    if not root.is_dir():
        return []
    found = list(root.glob(f"*/*{JSONL_SUFFIX}"))
    found += root.glob(f"*/*/{SUBAGENTS_DIR}/*{JSONL_SUFFIX}")
    return [p for p in found if _recent(p, now)]


DAY_FORMAT = "%Y/%m/%d"  # codex names day dirs in local time
DAY_S = 86400.0


def _day_dirs(now: float) -> List[Path]:
    """Today's and yesterday's codex day dirs (yesterday covers the midnight rollover)."""
    sessions = codex_home() / CODEX_DIRS[0]
    return [sessions / time.strftime(DAY_FORMAT, time.localtime(now - back))
            for back in (0.0, DAY_S)]


def _rollouts_in(directory: Path, now: float) -> List[Path]:
    try:
        with os.scandir(directory) as entries:
            return [Path(e.path) for e in entries
                    if e.name.startswith(ROLLOUT_PREFIX) and e.name.endswith(JSONL_SUFFIX)
                    and _recent(Path(e.path), now)]
    except OSError:
        return []


def watch_dirs(now: float) -> List[Path]:
    """Directories whose changes mean 'something to ingest'."""
    home = codex_home()
    found = [home / CODEX_DIRS[0], *_day_dirs(now), home / CODEX_DIRS[1]]
    for claude in claude_homes():
        found.append(claude / CLAUDE_SESSIONS)
        found += {p.parent for p in _claude_files(claude, now)}
    return [d for d in found if d.is_dir()]


def active_files(now: float) -> List[Path]:
    """Recently written sources; cheap: two day dirs + archived top level, no rglob."""
    files: List[Path] = []
    for directory in [*_day_dirs(now), codex_home() / CODEX_DIRS[1]]:
        files += _rollouts_in(directory, now)
    for claude in claude_homes():
        files += _claude_files(claude, now)
    return files


# ---------------------------------------------------------------- one cycle

def _files_digest(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for row in conn.execute("SELECT path, generation, offset, size, mtime_ns, inode"
                            " FROM files ORDER BY path"):
        digest.update(repr(tuple(row)).encode())
    return digest.hexdigest()


def _claude_scope(path: Path) -> str:
    return SCOPE_SUBAGENT if path.parent.name == SUBAGENTS_DIR else SCOPE_TRANSCRIPT


def _ingest_path(path: Path) -> None:
    if path.suffix != JSONL_SUFFIX or not path.is_file():
        return
    if CODEX_HOME_NAME in path.parts:
        from hh_ps.native_source import _classify
        from . import codex_ingest
        codex_ingest.sync(path, _classify)
        return
    from . import claude_ingest
    claude_ingest.sync(path, _claude_scope(path))


def _full_codex() -> None:
    home = codex_home()
    if not home.is_dir():
        return
    from hh_ps.machine_usage import _machine_rollouts
    from hh_ps.native_source import _classify
    from . import codex_ingest
    for path in _machine_rollouts(home):  # also forgets moved/deleted rollouts
        try:
            codex_ingest.sync(path, _classify)
        except OSError:  # vanished after the listing: skip it, keep sweeping the rest
            continue


# Digest at the end of the previous cycle, per state dir. Comparing with it (not with a
# digest taken at the start of this cycle) also bumps for rows a reader such as hh-ps
# ingested itself in between, so the other readers still hear about them.
_last_digest: Dict[str, str] = {}


def ingest_once(targets: Optional[Iterable[Path]] = None, full: bool = False) -> bool:
    """Ingest `targets` (and every source when `full`); bump revision on a real change.

    Returns True when the store changed since the previous cycle. The ingest lock is
    released before returning.
    """
    key = str(paths.state_dir())
    try:
        conn = runtime.connection()
        if conn is None:
            return False
        before = _last_digest.get(key) or _files_digest(conn)
        if full:
            _full_codex()
        for path in targets or ():
            try:
                _ingest_path(Path(path))
            except OSError:
                continue
        conn = runtime.connection()
        after = _files_digest(conn) if conn is not None else before
        changed = after != before
        _last_digest[key] = after
    except (OSError, sqlite3.Error, RuntimeError, ValueError):
        changed = False
    finally:
        runtime.release()
    if changed:
        paths.bump_revision()
    return changed


def drain_dirty(directory: Path) -> Set[Path]:
    """Paths queued by `hh-store touch --path`; entries are removed once read."""
    found: Set[Path] = set()
    for entry in paths.dirty_dir(directory).iterdir():
        try:
            found.update(Path(line) for line in entry.read_text().splitlines() if line)
            entry.unlink()
        except OSError:
            continue
    return found


# ---------------------------------------------------------------- daemon

class _Watcher:
    """kqueue vnode watches; `None` kqueue means stat polling only."""

    def __init__(self) -> None:
        self.kq = select.kqueue() if hasattr(select, "kqueue") else None
        self.fds: Dict[int, Path] = {}
        soft = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        self.limit = min(MAX_WATCH_FDS, max(soft, 0) // 2)

    def rebuild(self, targets: List[Path]) -> None:
        if self.kq is None:
            return
        self.close_fds()
        flags = 0
        for name in VNODE_FLAGS:
            flags |= getattr(select, f"KQ_{name}")
        for path in targets[: self.limit]:
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_EVTONLY", 0))
            except OSError:
                continue
            self.fds[fd] = path
            self.kq.control([select.kevent(fd, select.KQ_FILTER_VNODE,
                                           select.KQ_EV_ADD | select.KQ_EV_CLEAR, flags)], 0)

    def wait(self, timeout: float) -> Set[Path]:
        if self.kq is None:
            time.sleep(max(timeout, 0))
            return set()
        events = self.kq.control(None, KQ_BATCH, max(timeout, 0))
        return {self.fds[e.ident] for e in events if e.ident in self.fds}

    def close_fds(self) -> None:
        for fd in self.fds:
            os.close(fd)
        self.fds.clear()

    def close(self) -> None:
        self.close_fds()
        if self.kq is not None:
            self.kq.close()


def _expand_events(hit: Set[Path], directory: Path, now: float) -> Set[Path]:
    """Map watched paths to files to ingest; the dirty dir yields its queued paths."""
    out: Set[Path] = set()
    dirty = paths.dirty_dir(directory)
    for path in hit:
        if path == dirty:
            out |= drain_dirty(directory)
        elif path.is_dir():
            out |= {p for p in path.glob(f"*{JSONL_SUFFIX}") if _recent(p, now)}
        else:
            out.add(path)
    return out


def _idle(directory: Path, started: float, cfg: Config) -> bool:
    try:
        last = (directory / paths.LAST_READ_NAME).stat().st_mtime
    except OSError:
        last = started
    return time.time() - max(last, started) > cfg.idle_timeout


def _serve(directory: Path, cfg: Config, watcher: _Watcher) -> None:
    started = time.time()
    next_full = 0.0
    next_rollouts = 0.0
    pending: Set[Path] = set()
    while not _idle(directory, started, cfg):
        now = time.monotonic()
        if now >= next_full:
            files = active_files(time.time())
            full = now >= next_rollouts
            ingest_once(drain_dirty(directory) | set(files), full=full)
            if full:
                next_rollouts = time.monotonic() + cfg.rollout_scan
            watcher.rebuild([paths.dirty_dir(directory)] + watch_dirs(time.time()) + files)
            next_full = time.monotonic() + cfg.full_scan
            continue
        timeout = min(next_full - now, cfg.active_poll, cfg.idle_timeout)
        pending |= _expand_events(watcher.wait(timeout), directory, time.time())
        if watcher.kq is None:
            pending |= set(active_files(time.time())) | drain_dirty(directory)
        if not pending:
            continue
        deadline = time.monotonic() + cfg.debounce
        while (left := deadline - time.monotonic()) > 0:
            pending |= _expand_events(watcher.wait(left), directory, time.time())
        ingest_once(pending)
        pending = set()


def _on_signal(_signum: int, _frame: object) -> None:
    raise _Stop()


def run(cfg: Config) -> int:
    """Daemon body; returns 0 always (losing the singleton race included)."""
    directory = paths.state_dir()
    fd = os.open(directory / paths.INDEXER_LOCK_NAME, os.O_RDWR | os.O_CREAT, paths.FILE_MODE)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return 0
    watcher = _Watcher()
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    try:
        _serve(directory, cfg, watcher)
    except _Stop:
        pass
    finally:
        watcher.close()
        runtime.release()
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hh-indexer")
    parser.add_argument("--idle-timeout", type=float, default=IDLE_TIMEOUT_S)
    parser.add_argument("--debounce", type=float, default=DEBOUNCE_S)
    parser.add_argument("--full-scan", type=float, default=FULL_SCAN_S)
    parser.add_argument("--active-poll", type=float, default=ACTIVE_POLL_S)
    parser.add_argument("--rollout-scan", type=float, default=ROLLOUT_SCAN_S)
    args = parser.parse_args(argv)
    if not runtime.enabled():
        return 0
    return run(Config(idle_timeout=args.idle_timeout, debounce=args.debounce,
                      full_scan=args.full_scan, rollout_scan=args.rollout_scan,
                      active_poll=args.active_poll))
