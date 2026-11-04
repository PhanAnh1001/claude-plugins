"""JSON file guarded by an fcntl lock on a sibling .lock file, written atomically."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

LOCK_SUFFIX = ".lock"


@contextmanager
def locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + LOCK_SUFFIX), "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_json(path: Path, empty: Any) -> Any:
    if not path.is_file():
        return empty
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return empty
    data = json.loads(text)
    if not isinstance(data, type(empty)):
        raise ValueError(f"{path}: cần JSON {type(empty).__name__}")
    return data


def write_atomic(path: Path, data: Any) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
