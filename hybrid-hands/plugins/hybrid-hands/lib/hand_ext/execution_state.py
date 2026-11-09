"""Versioned durable execution intent. No process liveness is inferred here."""
from __future__ import annotations
import dataclasses
import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Optional

class StateConflict(RuntimeError): pass
class StateCorrupt(RuntimeError): pass

def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)): return tuple(_freeze(v) for v in value)
    if value is None or type(value) in (str, int, float, bool): return value
    raise ValueError('options must be JSON values')

def _plain(value):
    if dataclasses.is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (dict, MappingProxyType)): return {k: _plain(v) for k,v in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value

@dataclass(frozen=True)
class Invocation:
    invocation_id: str
    scope_id: str
    parent_session: str
    parent_paseo_agent_id: Optional[str] = None
    backend: str = ''
    account_alias: str = ''
    model: str = ''
    effort: str = ''
    origin: str = 'managed'
    source_cwd: str = ''
    isolated_cwd: str = ''
    fixed_options: dict = field(default_factory=dict)
    resource_claims: tuple = ()
    version: int = 1
    def __post_init__(self):
        if self.version != 1 or not self.invocation_id or not self.scope_id: raise ValueError('invalid invocation')
        if self.origin not in ('shell','managed','native_intent','legacy_native'): raise ValueError('invalid origin')
        # Copy recursively, validate serializability, and prevent alias mutation.
        json.dumps(_plain(self.fixed_options), allow_nan=False)
        object.__setattr__(self, 'fixed_options', _freeze(dict(self.fixed_options)))
        object.__setattr__(self, 'resource_claims', tuple(sorted(set(self.resource_claims))))

@dataclass(frozen=True)
class ExecutionKey:
    invocation_id: str
    attempt_id: str
    epoch: int

@dataclass(frozen=True)
class Attempt:
    invocation_id: str
    attempt_id: str
    epoch: int
    request_key: str
    run_id: Optional[str] = None
    target_key: Optional[str] = None
    project_id: Optional[str] = None
    workspace_id: Optional[str] = None
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    def __post_init__(self):
        if type(self.epoch) is not int or self.epoch < 1 or not self.request_key or not self.attempt_id: raise ValueError('invalid attempt')
    @property
    def key(self): return ExecutionKey(self.invocation_id, self.attempt_id, self.epoch)

@dataclass
class ExecutionRecord:
    invocation: Invocation
    attempt: Attempt
    state: str = 'intent'
    revision: int = 0
    version: int = 1
    writer: Optional[dict] = None
    process: Optional[dict] = None
    receipt: Optional[dict] = None
    outcome: Optional[dict] = None
    artifacts: dict = field(default_factory=dict)
    settle_keys: dict = field(default_factory=dict)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    reservation: Optional[dict] = None
    pending_outcome: Optional[dict] = None
    quiescence: Optional[dict] = None
    @property
    def key(self): return self.attempt.key
    def to_dict(self): return _plain(self)
    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data['invocation'] = Invocation(**data['invocation'])
        data['attempt'] = Attempt(**data['attempt'])
        record = cls(**data)
        if record.version != 1 or record.revision < 0 or record.invocation.invocation_id != record.attempt.invocation_id: raise ValueError('invalid record')
        return record

def as_key(key): return key if isinstance(key, ExecutionKey) else ExecutionKey(*key)

def atomic_json(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, allow_nan=False, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if os.path.exists(name): os.unlink(name)

class ExecutionStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    @contextmanager
    def locked(self):
        with (self.root / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    def _path(self, key):
        key = as_key(key)
        return self.root / (hashlib.sha256(json.dumps(_plain(key), sort_keys=True).encode()).hexdigest()+'.json')
    def _read(self, path):
        try: return ExecutionRecord.from_dict(json.loads(path.read_text()))
        except FileNotFoundError: raise
        except Exception as exc: raise StateCorrupt('invalid execution state') from exc
    def create_intent(self, invocation, attempt):
        record = ExecutionRecord(invocation, attempt)
        if invocation.invocation_id != attempt.invocation_id: raise StateConflict('invocation mismatch')
        with self.locked():
            path = self._path(attempt.key)
            if path.exists():
                old = self._read(path)
                if old.invocation != invocation or old.attempt != attempt: raise StateConflict('identity already exists')
                return old
            for path in self.root.glob('*.json'):
                old = self._read(path)
                if old.attempt.request_key == attempt.request_key: raise StateConflict('request key reused')
                if old.invocation.invocation_id == invocation.invocation_id and old.invocation != invocation: raise StateConflict('invocation immutable')
            atomic_json(self._path(attempt.key), record.to_dict())
            return record
    def get(self, invocation_id, attempt_id=None, epoch=None):
        key = invocation_id if attempt_id is None else ExecutionKey(invocation_id, attempt_id, epoch)
        with self.locked(): return self._read(self._path(key))
    def compare_and_swap(self, key, expected_revision, updated):
        with self.locked():
            path = self._path(key); old = self._read(path)
            if old.revision != expected_revision: raise StateConflict('revision conflict')
            if updated.key != old.key or updated.invocation != old.invocation: raise StateConflict('identity immutable')
            for f in dataclasses.fields(Attempt):
                before, after = getattr(old.attempt,f.name), getattr(updated.attempt,f.name)
                if before is not None and before != after: raise StateConflict('attempt binding immutable')
            if old.outcome is not None and old.outcome != updated.outcome: raise StateConflict('outcome immutable')
            result = ExecutionRecord.from_dict(updated.to_dict())
            result.revision = old.revision + 1
            atomic_json(path, result.to_dict()); return result
    def bind_placement(self, key, expected_revision, placement):
        record = self.get(key)
        if not isinstance(placement, dict): placement = _plain(placement)
        allowed = {'target_key','project_id','workspace_id','agent_id','thread_id'}
        if set(placement)-allowed: raise ValueError('invalid placement fields')
        record.attempt = dataclasses.replace(record.attempt, **placement)
        return self.compare_and_swap(key, expected_revision, record)
    def list_unsettled(self, scope_id=None):
        with self.locked():
            records = [self._read(p) for p in self.root.glob('*.json')]
        return [r for r in records if (scope_id is None or r.invocation.scope_id == scope_id) and (r.reservation or r.state not in ('archived','awaiting_review','failed','not_admitted'))]
