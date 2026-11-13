"""Private atomic journal; hold its flock through identity check and dispatch."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def state_path():
    return Path.home() / '.hybrid-hands/limit-watch/state.json'


def empty():
    return dict(version=1, enabled=False, persistent=False, generation=0, targets={})


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else state_path()

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(self.path.with_suffix('.lock')), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as lock:
            # A tick is finite; another scheduler tick does not queue behind it.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self):
        if not self.path.exists():
            return empty()
        data = json.loads(self.path.read_text())
        if (not isinstance(data, dict) or data.get('version') != 1
                or not isinstance(data.get('targets'), dict)
                or type(data.get('generation')) is not int):
            raise ValueError('invalid_watch_state')
        return data

    def save(self, data):
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.state-')
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out, ensure_ascii=False, allow_nan=False, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
            # Also persist the rename before any external side effect.
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
