"""Kernel-owned, nonblocking slots for a complete hand run in one Sol scope."""
from __future__ import annotations

import fcntl
import hashlib
import os
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


@contextmanager
def reserve_slot(root: Path, limit: int) -> Iterator[None]:
    """Keep one descriptor through retries; close/OS process exit releases it.

    The per-user OS temp directory deliberately does not follow registry state:
    an unwritable registry must still only warn. Never unlink lock files, since
    replacing an inode would let another caller bypass its existing lock.
    Python opens descriptors non-inheritable, so backend execs cannot retain one.
    """
    limit = validate_limit(limit)
    directory = (Path(tempfile.gettempdir()) / f"{SLOTS_DIR_PREFIX}{os.getuid()}"
                 / scope_digest(root))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for index in range(limit):
        slot = (directory / f"{index}.lock").open("a")
        try:
            fcntl.flock(slot.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            slot.close()
            continue
        except BaseException:
            slot.close()
            raise
        try:
            yield
        finally:
            slot.close()
        return
    raise ParallelFull(f"đã đủ {limit} hand-ext run đồng thời trong phiên Sol này; "
                       "hãy chờ một lượt kết thúc rồi thử lại (exit 8)")
