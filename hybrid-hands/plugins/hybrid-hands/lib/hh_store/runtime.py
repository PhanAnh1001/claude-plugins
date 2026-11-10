"""Process-wide store access: holds the ingest lock for the process lifetime."""
from __future__ import annotations

import atexit
import contextlib
import os
import sqlite3
from typing import Optional

from .db import open_store
from .paths import ingest_lock

STORE_ENV = "HYBRID_HANDS_STORE"
DISABLED_VALUES = frozenset({"0", "off", "false", "no"})
LOCK_TIMEOUT_SECONDS = 5.0

_UNSET = object()
_conn: object = _UNSET  # _UNSET, None (disabled for this process) or a Connection
_lock_stack: Optional[contextlib.ExitStack] = None


def enabled() -> bool:
    return os.environ.get(STORE_ENV, "").strip().lower() not in DISABLED_VALUES


def _release() -> None:
    global _lock_stack
    if _lock_stack is not None:
        _lock_stack.close()
        _lock_stack = None


def _open() -> Optional[sqlite3.Connection]:
    global _lock_stack
    stack = contextlib.ExitStack()
    try:
        if not stack.enter_context(ingest_lock(timeout=LOCK_TIMEOUT_SECONDS)):
            stack.close()
            return None
        conn = open_store()
    except (OSError, sqlite3.Error):
        stack.close()
        return None
    _lock_stack = stack
    atexit.register(_release)
    return conn


def connection() -> Optional[sqlite3.Connection]:
    """Cached store connection, or None -> caller uses the legacy file path."""
    global _conn
    if _conn is _UNSET:
        _conn = _open() if enabled() else None
    return _conn  # type: ignore[return-value]


def disable_after_error(exc: BaseException) -> None:
    """Switch the whole process to the legacy path after a mid-run store error."""
    global _conn
    if isinstance(_conn, sqlite3.Connection):
        with contextlib.suppress(sqlite3.Error):
            _conn.close()
    _conn = None
    _release()


def release() -> None:
    """Close the connection and free the ingest lock; the next connection() reopens.

    Long-running writers (hh-indexer) call this after each cycle so hh-ps never waits.
    """
    global _conn
    disable_after_error(RuntimeError("release"))
    _conn = _UNSET


def _reset_for_tests() -> None:
    release()
