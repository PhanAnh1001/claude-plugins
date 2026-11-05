"""Detached-worker helpers shared by `paseo --self` and `term --self`."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import List

from .constants import (
    BIN_SUBDIR, EXIT_NOT_FOUND, EXIT_USAGE, HANDOFF_SUBDIR, SELF_ENTRY_NAME,
    SELF_LOG_PREFIX, SELF_LOG_SUFFIX, SELF_LOG_TIME_FORMAT,
    SELF_MAX_WAIT_SECONDS, SELF_MIN_SLEEP_SECONDS, SELF_POLL_SECONDS,
)
from .errors import CcSwitchError
from .paths import short_id, state_dir


def stamp() -> str:
    return time.strftime(SELF_LOG_TIME_FORMAT)


def log(message: str) -> None:
    print(f"[{stamp()}] {message}", flush=True)


def check_duration(name: str, value: int) -> None:
    if value < 0:
        raise CcSwitchError(f"{name} phải là số nguyên không âm.", EXIT_USAGE)


def worker_log_path(session_id: str) -> Path:
    """One log per session, shared by both `--self` directions."""
    name = f"{SELF_LOG_PREFIX}{short_id(session_id)}{SELF_LOG_SUFFIX}"
    return state_dir() / HANDOFF_SUBDIR / name


def entry_path() -> str:
    """The real `bin/cc-switch` beside this plugin, else the current script."""
    candidate = Path(__file__).resolve().parents[2] / BIN_SUBDIR / SELF_ENTRY_NAME
    if candidate.is_file():
        return str(candidate)
    path = Path(sys.argv[0])
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path)


def spawn_worker(argv: List[str], log_path: Path, cwd: str,
                 header: str) -> subprocess.Popen:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(log_path, "a", encoding="utf-8")
    except OSError as exc:
        raise CcSwitchError(
            f"Không mở được file log {log_path}: {exc}", EXIT_NOT_FOUND) from exc
    try:
        handle.write(f"[{stamp()}] {header}\n")
        handle.flush()
        return subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=handle,
            stderr=subprocess.STDOUT, start_new_session=True,
            cwd=cwd, close_fds=True,
        )
    except OSError as exc:
        raise CcSwitchError(
            f"Không tách được tiến trình nền: {exc}\nLog: {log_path}",
            EXIT_NOT_FOUND) from exc
    finally:
        handle.close()


def wait_for_idle(path: Path, idle_seconds: float,
                  max_wait_seconds: float = SELF_MAX_WAIT_SECONDS,
                  poll_seconds: float = SELF_POLL_SECONDS) -> bool:
    """True once the transcript mtime is at least `idle_seconds` old."""
    deadline = time.monotonic() + max_wait_seconds
    while True:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False
        if time.time() - mtime >= idle_seconds:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(max(min(poll_seconds, remaining), SELF_MIN_SLEEP_SECONDS))
