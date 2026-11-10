"""State directory, ingest lock and revision counter."""
from __future__ import annotations

import contextlib
import fcntl
import os
import time
from pathlib import Path
from typing import Iterator, Optional

STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
DIR_MODE = 0o700
FILE_MODE = 0o600
INGEST_LOCK_NAME = "ingest.lock"
REVISION_NAME = "revision"
REVISION_LOCK_NAME = "revision.lock"
LOCK_RETRY_SECONDS = 0.05  # short poll keeps a 5 s wait responsive without busy-spinning


def state_dir() -> Path:
    """Return (and create, 0700) the store directory."""
    override = os.environ.get(STATE_DIR_ENV)
    path = Path(override) if override else Path.home() / ".hybrid-hands" / "state"
    path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    os.chmod(path, DIR_MODE)
    return path


def _open_lock(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT, FILE_MODE)


@contextlib.contextmanager
def ingest_lock(timeout: float = 5.0, directory: Optional[Path] = None) -> Iterator[bool]:
    """Yield True while holding LOCK_EX on ingest.lock, False if timeout expired."""
    fd = _open_lock((directory or state_dir()) / INGEST_LOCK_NAME)
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(LOCK_RETRY_SECONDS)
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _parse_revision(path: Path) -> int:
    try:
        return int(path.read_text().strip() or 0)
    except (OSError, ValueError):
        return 0


def read_revision(directory: Optional[Path] = None) -> int:
    """Current revision number; 0 when missing or corrupt."""
    try:
        return _parse_revision((directory or state_dir()) / REVISION_NAME)
    except OSError:
        return 0


def bump_revision(directory: Optional[Path] = None) -> None:
    """Atomically increment the revision file. Never raises: writers must not fail on it."""
    try:
        base = Path(directory) if directory else state_dir()
        fd = _open_lock(base / REVISION_LOCK_NAME)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            target = base / REVISION_NAME
            tmp = base / f".{REVISION_NAME}.{os.getpid()}.tmp"
            tmp.write_text(f"{_parse_revision(target) + 1}\n")
            os.chmod(tmp, FILE_MODE)
            os.replace(tmp, target)
        finally:
            os.close(fd)
    except Exception:  # noqa: BLE001 - contract: bump is best-effort, never breaks writers
        return
