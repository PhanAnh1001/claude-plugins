"""Kernel-owned, nonblocking slots for a complete hand run in one Sol scope."""
from __future__ import annotations

import fcntl
import hashlib
import os
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .constants import HAND_SCOPE_ENV, MAX_PARALLEL, PARENT_SESSION_ENV

SCOPE_ENV_ORDER = (HAND_SCOPE_ENV, "CODEX_THREAD_ID", PARENT_SESSION_ENV)
SLOTS_DIR_PREFIX = "hybrid-hands-slots-"


class ParallelFull(Exception):
    """Every slot allowed for this scope is already held."""


def validate_limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_PARALLEL:
        raise ValueError(f"ext_hand.max_parallel phải là số nguyên 1..{MAX_PARALLEL} "
                         "(không nhận bool)")
    return value


def scope_digest(root: Path) -> str:
    for name in SCOPE_ENV_ORDER:
        value = os.environ.get(name)
        if value:
            scope = f"{name}:{value}"
            break
    else:
        scope = f"repo:{root.resolve()}"
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()


def pool_root() -> Path:
    return Path(tempfile.gettempdir()) / f"{SLOTS_DIR_PREFIX}{os.getuid()}"


def canonical_scope(scope_id: str) -> str:
    """Explicit scope IDs use the same HAND_SCOPE_ENV namespace as shell.

    scope_digest(root) results are accepted unchanged for compatibility. Raw
    IDs are hashed; empty IDs and path-shaped IDs are rejected, never paths.
    """
    import re
    if not isinstance(scope_id, str) or not scope_id or scope_id in ('.', '..') or '/' in scope_id or '\\' in scope_id:
        raise ValueError('invalid scope identifier; use scope_digest(root) for path scopes')
    if re.fullmatch(r'[0-9a-f]{64}', scope_id): return scope_id
    return hashlib.sha256(f'{HAND_SCOPE_ENV}:{scope_id}'.encode()).hexdigest()


def pool_scope(scope_id: str) -> Path:
    return pool_root() / canonical_scope(scope_id)


@contextmanager
def pool_lock():
    root = pool_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / '.admission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def durable_reservations():
    # Corrupt reservation data fails closed for shell and managed callers alike.
    for path in pool_root().glob('*/reservation-*.json'):
        yield path, json.loads(path.read_text())


def shell_count(directory):
    count = 0
    for path in directory.glob('*.lock'):
        with path.open('a') as stream:
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: count += 1
    return count


@contextmanager
def reserve_slot(root: Path, limit: int) -> Iterator[None]:
    """Kernel-owned shell slot, sharing admission with durable managed writers."""
    limit = validate_limit(limit)
    directory = pool_scope(scope_digest(root))
    slot = None
    with pool_lock():
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        durable = sum(1 for _, r in durable_reservations()
                      if canonical_scope(r['scope_id']) == directory.name)
        if shell_count(directory) + durable < limit:
            for index in range(limit):
                candidate = (directory / f"{index}.lock").open('a')
                try: fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    candidate.close(); continue
                slot = candidate; break
    if slot is None:
        raise ParallelFull(f"đã đủ {limit} hand-ext run đồng thời trong phiên Sol này; "
                           "hãy chờ một lượt kết thúc rồi thử lại (exit 8)")
    try: yield
    finally: slot.close()
