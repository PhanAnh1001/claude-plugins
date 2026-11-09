"""Durable, single-launch worker. Recovery observes; it never replays a launch.

Hooks are a mapping of artifact kind to (key, idempotency_key, record, outcome)
callbacks. The record carries prepared isolated_cwd, receipt.worker_run_dir (the unique
attempt/epoch log directory), and existing artifact refs.
A hook interrupted after its durable in_progress marker is NOT retried: G3 must
reconcile the external sink by its idempotency key before marking completion.
No admission release or source apply policy is implemented here.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import uuid

from .backends import get_backend
from .backends.base import RunSpec
from .constants import DEFAULTS, SANDBOXES
from .execution_state import ExecutionKey, StateConflict, as_key, _plain
from .execution_supervisor import ProcessIdentity, Quiescence, ConservativeProcessOps
from .parallel import scope_digest
from .runner import run_backend


@dataclass(frozen=True)
class WorkerHandle:
    key: ExecutionKey
    owner_id: str
    process_identity: ProcessIdentity | None = None


@dataclass(frozen=True)
class WorkerOutcome:
    key: ExecutionKey
    status: str
    reason: str = ''
    backend_exit_code: int | None = None
    provenance: str = ''
    quiescence: Quiescence | None = None
    usage: dict | None = None
    artifact_refs: dict = field(default_factory=dict)
    quiescent: bool = False
    final_text: str = ''


@dataclass(frozen=True)
class WorkerObservation:
    state: str
    quiescence: Quiescence | None
    outcome: WorkerOutcome | None


class OwnedProcessOps:
    """Authority is retained Popen ownership, never a recovered numeric PID.

    Absence of the entire owned group AND a reaped leader certify quiescence.
    A surviving/escaped descendant cannot be certified by leader exit alone.
    Backends must keep descendants in the session/group created by the runner.
    """
    def __init__(self, fallback=None):
        self.fallback = fallback or ConservativeProcessOps()
        self.owned = {}
        self.lock = threading.RLock()

    def add(self, proc):
        identity = ProcessIdentity(proc.pid, proc.pid, uuid.uuid4().hex)
        with self.lock:
            self.owned[identity] = [proc, False]
        return identity

    def reconcile(self, identity):
        with self.lock:
            entry = self.owned.get(identity)
            if entry is None:
                return self.fallback.reconcile(identity)
            proc, stopped = entry
            if not stopped:
                proc.poll()
                try:
                    os.killpg(identity.pgid, 0)
                except ProcessLookupError:
                    stopped = proc.returncode is not None
                    entry[1] = stopped
                except PermissionError:
                    pass
            return Quiescence(stopped, 'owned group absent and leader reaped' if stopped
                              else 'owned group not quiescent', time.time())

    def cancel(self, identity, reason):
        with self.lock:
            entry = self.owned.get(identity)
            if entry is None:
                return self.fallback.cancel(identity, reason)
            proc, stopped = entry
            if stopped or proc.returncode is not None:
                # Reaped leader: its numeric group may have been reused. Never
                # signal without a retained live/unreaped ownership identity.
                return self.reconcile(identity)
            try:
                if os.getpgid(proc.pid) != identity.pgid:
                    return Quiescence(False, 'owned leader changed group', time.time())
                os.killpg(identity.pgid, signal.SIGTERM)
                # Keep the leader UNREAPED through escalation. Its reserved PID
                # prevents PGID reuse, even if TERM already killed the leader.
                # Runner poll/wait operations share this ownership lock.
                time.sleep(.3)
                os.killpg(identity.pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                # macOS may reject signalling a group containing only the
                # unreaped zombie leader. Reap, then verify group absence.
                pass
            try:
                proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                pass
            until = time.monotonic() + .5
            while time.monotonic() < until:
                q = self.reconcile(identity)
                if q.confirmed:
                    return q
                time.sleep(.01)
            return self.reconcile(identity)


class _Control:
    def __init__(self, worker, key, owner):
        self.worker, self.key, self.owner = worker, key, owner
        self.cancelled = threading.Event()
        self.identity = None
        self.reason = ''

    def spawned(self, proc):
        self.identity = self.worker.process_ops.add(proc)
        with self.worker.lock:
            self.worker.supervisor.register_writer(self.key, self.identity, self.owner)
        if self.cancelled.is_set():
            self.stop(proc)

    def poll(self, proc):
        with self.worker.process_ops.lock:
            return proc.poll()

    def wait(self, proc, timeout):
        with self.worker.process_ops.lock:
            return proc.wait(timeout=timeout)

    def stop(self, proc):
        if self.identity is not None:
            return self.worker.process_ops.cancel(self.identity, self.reason or 'runner cleanup')


class ExecutionWorker:
    def __init__(self, store, supervisor, runner=None, settlement_hooks=None):
        self.store, self.supervisor = store, supervisor
        self.runner = runner or run_backend
        self.hooks = dict(settlement_hooks or {})
        self.lock = threading.RLock()
        self.controls = {}
        self.process_ops = OwnedProcessOps(supervisor.process_ops)
        supervisor.process_ops = self.process_ops

    def _spec(self, invocation, attempt, brief):
        if invocation.backend not in ('codex', 'dsh', 'claude-v1', 'claude-v2'):
            raise ValueError('fixed supported backend required')
        if invocation.scope_id != scope_digest(Path(invocation.source_cwd)):
            raise ValueError('scope must be source root digest')
        if not invocation.model or not invocation.effort:
            raise ValueError('fixed model and effort required')
        if invocation.backend in ('codex', 'dsh') and invocation.account_alias not in ('', invocation.backend):
            raise ValueError('fixed account must match backend')
        if invocation.backend.startswith('claude-') and invocation.account_alias not in (invocation.backend, invocation.backend.removeprefix('claude-')):
            raise ValueError('fixed Claude account must match backend')
        cwd = Path(invocation.isolated_cwd)
        if not invocation.isolated_cwd or not cwd.is_dir() or cwd.resolve() == Path(invocation.source_cwd).resolve():
            raise ValueError('prepared isolated cwd required')
        opts = _plain(invocation.fixed_options)
        allowed = {'run_dir','sandbox','timeout_s','max_tokens','browser','options'}
        if set(opts) - allowed:
            raise ValueError('unsupported fixed option')
        required = {'run_dir','sandbox','timeout_s','max_tokens'}
        if not required <= opts.keys():
            raise ValueError('explicit run limits and sandbox required')
        if opts['sandbox'] not in SANDBOXES:
            raise ValueError('invalid sandbox')
        if type(opts['timeout_s']) not in (int, float) or opts['timeout_s'] <= 0:
            raise ValueError('invalid timeout')
        if opts['max_tokens'] is not None and (type(opts['max_tokens']) is not int or opts['max_tokens'] <= 0):
            raise ValueError('invalid token cap')
        if 'browser' in opts and type(opts['browser']) is not bool:
            raise ValueError('invalid browser flag')
        if opts.get('browser') and invocation.backend != 'dsh':
            raise ValueError('browser requires dsh')
        backend_opts = opts.get('options', {})
        config_name = {'claude-v1': 'claude-main', 'claude-v2': 'claude'}.get(invocation.backend, invocation.backend)
        supported = set(DEFAULTS['backends'][config_name]) | {'sandbox'}
        if invocation.backend.startswith('claude-'):
            supported |= {'append_system_prompt'}
        if invocation.backend == 'dsh':
            supported |= {'browser_dir'}
        if not isinstance(backend_opts, dict) or set(backend_opts) - supported:
            raise ValueError('unsupported backend option')
        for field_name, fixed in (('model', invocation.model), ('effort', invocation.effort), ('sandbox', opts['sandbox'])):
            if field_name in backend_opts and backend_opts[field_name] != fixed:
                raise ValueError('backend option conflicts with fixed invocation')
        if 'max_turns' in backend_opts and (type(backend_opts['max_turns']) is not int or backend_opts['max_turns'] <= 0):
            raise ValueError('invalid max_turns')
        suffix = hashlib.sha256(json.dumps(_plain(attempt.key), sort_keys=True).encode()).hexdigest()
        run_dir = Path(opts['run_dir']).resolve() / suffix
        if self.store.root == run_dir or self.store.root.is_relative_to(run_dir) or self.store.root.is_relative_to(cwd.resolve()) or run_dir.is_relative_to(self.store.root):
            raise ValueError('state store must remain outside writer directory')
        return RunSpec(brief, cwd, run_dir, invocation.model, invocation.effort,
                       opts['sandbox'], opts['timeout_s'], opts['max_tokens'], backend_opts,
                       opts.get('browser', False))

    def start(self, invocation, attempt, brief):
        key = attempt.key
        record = self.store.get(key)
        if record.invocation != invocation:
            raise StateConflict('fixed invocation mismatch')
        spec = self._spec(invocation, record.attempt, brief)
        with self.lock:
            while True:
                record = self.store.get(key)  # placement may have been bound since caller read
                if record.receipt and record.receipt.get('worker_owner'):
                    identity = ProcessIdentity(**{k:record.process[k] for k in ('pid','pgid','start_identity')}) if record.process else None
                    return WorkerHandle(key, record.receipt['worker_owner'], identity)
                if not record.reservation:
                    raise StateConflict('admission reservation required')
                if record.reservation.get('key') != _plain(key) or record.reservation.get('scope_id') != invocation.scope_id:
                    raise StateConflict('reservation identity mismatch')
                owner = uuid.uuid4().hex
                record.receipt = dict(record.receipt or {}, worker_owner=owner, worker_run_dir=str(spec.run_dir))
                record.state = 'launching'
                try:
                    self.store.compare_and_swap(key, record.revision, record)
                    break
                except StateConflict:
                    continue
            control = _Control(self, key, owner)
            self.controls[key] = control
            thread = threading.Thread(target=self._run, args=(key, spec, control), daemon=True)
            thread.start()
            return WorkerHandle(key, owner)

    def _run(self, key, spec, control):
        try:
            result = self.runner(get_backend(self.store.get(key).invocation.backend), spec, control=control)
            # Default Usage() is not evidence of observed token usage.
            usage = asdict(result.state.usage) if result.state.usage.total() or result.state.usage.cached_input else None
            outcome = dict(status='cancelled' if control.cancelled.is_set() else result.status.value,
                           reason=control.reason, backend_exit_code=result.exit_code,
                           provenance='runner', usage=usage, final_text=result.state.final_text)
        except Exception:
            if control.identity is not None:
                self.process_ops.cancel(control.identity, 'runner exception')
            outcome = dict(status='failed', reason='runner exception', backend_exit_code=None,
                           provenance='worker_exception', usage=None)
        with self.lock:
            self.supervisor.record_outcome_once(key, outcome)
            self._settle(key)

    def _settle(self, key):
        record = self.store.get(key)
        if record.outcome is None or not self.hooks:
            return
        for kind, hook in self.hooks.items():
            record = self.store.get(key)
            marker = record.settle_keys.get(kind)
            if marker:
                if marker['state'] != 'completed':
                    return  # crash/ambiguous callback requires explicit external reconciliation
                continue
            token = hashlib.sha256(json.dumps([_plain(key), kind], sort_keys=True).encode()).hexdigest()
            record.settle_keys[kind] = dict(key=token, state='in_progress')
            record = self.store.compare_and_swap(key, record.revision, record)
            try:
                refs = hook(key, token, record, self.outcome(key))
            except Exception:
                return  # never blindly replay an external side effect
            record = self.store.get(key)
            record.artifacts[kind] = refs
            record.settle_keys[kind] = dict(key=token, state='completed')
            self.store.compare_and_swap(key, record.revision, record)
        # Deliberately keep reservation + settling. G3 owns admission.release.

    def cancel(self, key, reason):
        key = as_key(key)
        with self.lock:
            control = self.controls.get(key)
            if control:
                control.reason = reason
                control.cancelled.set()
            q = self.supervisor.cancel(key, reason)
            return q

    def reconcile(self, key):
        key = as_key(key)
        with self.lock:
            q = self.supervisor.reconcile(key)
            record = self.store.get(key)
            if q.confirmed and record.pending_outcome is not None:
                self.supervisor.record_outcome_once(key, record.pending_outcome)
            self._settle(key)
            return WorkerObservation(self.store.get(key).state, q, self.outcome(key))

    def outcome(self, key):
        record = self.store.get(as_key(key))
        if record.outcome is None:
            return None
        data = dict(record.outcome)
        data['key'] = record.key
        data['quiescence'] = Quiescence(**record.quiescence) if record.quiescence else None
        data['artifact_refs'] = dict(record.artifacts)
        return WorkerOutcome(**data)
