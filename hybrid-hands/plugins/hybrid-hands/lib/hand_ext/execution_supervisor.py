"""Writer authority: only explicit identity-aware group evidence frees a slot."""
from dataclasses import dataclass, asdict
import os
import time
from .execution_state import StateConflict

@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    pgid: int
    start_identity: str

@dataclass(frozen=True)
class Quiescence:
    confirmed: bool
    evidence: str
    observed_at: float

class ConservativeProcessOps:
    """No arbitrary PID signalling; platform runners inject owned group operations.

    process_ops.reconcile(identity) and .cancel(identity, reason) must return
    Quiescence backed by identity verification AND group stop/reap evidence.
    PID absence, kill success and a reaped leader alone are insufficient.
    """
    def reconcile(self, identity):
        return Quiescence(False, 'group quiescence not established', time.time())
    def cancel(self, identity, reason):
        return self.reconcile(identity)

class ExecutionSupervisor:
    def __init__(self, store, process_ops=None):
        self.store = store
        self.process_ops = process_ops or ConservativeProcessOps()
    def register_writer(self, key, process_identity, owner_id):
        if not isinstance(process_identity, ProcessIdentity) or process_identity.pid <= 0 or process_identity.pgid <= 0 or not process_identity.start_identity:
            raise ValueError('verified process identity required')
        r = self.store.get(key)
        process = dict(asdict(process_identity), supervisor_id=str(os.getpid()))
        if r.writer:
            if r.writer['owner_id'] != owner_id or r.process != process: raise StateConflict('writer already bound')
            return
        if not r.reservation: raise StateConflict('writer requires admission')
        r.process = process
        r.writer = dict(owner_id=owner_id, kind='process_group', observed_at=time.time())
        r.state = 'running'; r.started_at = time.time()
        self.store.compare_and_swap(key, r.revision, r)
    def _observe(self, key, reason=None):
        r = self.store.get(key)
        if r.process:
            identity = ProcessIdentity(**{k:r.process[k] for k in ('pid','pgid','start_identity')})
            q = self.process_ops.reconcile(identity) if reason is None else self.process_ops.cancel(identity, reason)
        else: q = Quiescence(False, 'writer authority not established', time.time())
        if not isinstance(q, Quiescence) or (q.confirmed and not q.evidence): raise ValueError('invalid quiescence evidence')
        r.quiescence = asdict(q)
        if not q.confirmed: r.state = 'unresolved'
        self.store.compare_and_swap(key, r.revision, r)
        return q
    def cancel(self, key, reason): return self._observe(key, reason)
    def reconcile(self, key): return self._observe(key)
    def record_outcome_once(self, key, outcome):
        r = self.store.get(key)
        if r.outcome is not None: return r
        if not isinstance(outcome, dict):
            outcome = asdict(outcome)
        outcome = dict(outcome)
        outcome.pop('key', None)
        outcome.setdefault('backend_exit_code', None)
        outcome.setdefault('provenance', '')
        q = outcome.get('quiescent', False)
        if not q:
            supplied = outcome.get('quiescence')
            q = isinstance(supplied, dict) and supplied.get('confirmed') is True
        # Only supervisor's injected authority can certify termination.
        confirmed = self.reconcile(key).confirmed
        r = self.store.get(key)
        outcome['quiescent'] = confirmed
        if confirmed:
            r.outcome = outcome
            r.pending_outcome = None
        else:
            r.pending_outcome = outcome
        r.state = 'settling' if confirmed else 'unresolved'
        if confirmed: r.finished_at = time.time()
        try: return self.store.compare_and_swap(key, r.revision, r)
        except StateConflict:
            current = self.store.get(key)
            if current.outcome is not None: return current
            raise
