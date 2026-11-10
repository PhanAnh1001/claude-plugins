"""Writer authority: only explicit identity-aware group evidence frees a slot."""
from dataclasses import dataclass, asdict, field
import os
import time
from .execution_state import StateConflict
from .process_containment import merge_evidence

STATE_CAS_ATTEMPTS = 8
# Quiescence evidence when sticky incomplete containment is re-proved stale.
STALE_UNCERTAINTY_METHOD = 'stale_uncertainty_reproved'

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
    details: dict = field(default_factory=dict)

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
    # Read-only OS view for re-proving stale uncertainty; None means the live table.
    table = None

    def __init__(self, store, process_ops=None, table=None):
        self.store = store
        self.process_ops = process_ops or ConservativeProcessOps()
        if table is not None:
            self.table = table

    def _reprove_stale(self, r, containment):
        """Fresh proof that every incomplete observation is stale; None keeps fail-closed.

        Requires reaped root, root/owner/group/every tracked pid gone or reused, and a
        whole same-uid marker scan with no marker and no unreadable live environment.
        """
        if (not r.process or not isinstance(containment, dict)
                or containment.get('inventory_complete') is not False
                or containment.get('root_reaped') is not True):
            return None
        from .operator_reconcile import check_processes, scan_markers
        from .post_hoc_reverify import bindings
        if not containment.get('binding') or containment['binding'] != bindings(r):
            return None
        from .process_containment import ProcessTable
        table = self.table or ProcessTable()
        try:
            evidence = check_processes(r, containment, table)
            evidence.update(scan_markers(r, table))
        except Exception:
            return None  # any doubt (live pid, marker, unreadable env, OS error) blocks
        return Quiescence(True, STALE_UNCERTAINTY_METHOD, time.time(),
                          dict(containment, inventory_complete=True, stale_resolution=evidence))
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
        fence = getattr(self.process_ops, 'strict_revision_fence', False)
        fenced_revision = r.revision if fence else None
        if r.process:
            identity = ProcessIdentity(**{k:r.process[k] for k in ('pid','pgid','start_identity')})
            q = self.process_ops.reconcile(identity) if reason is None else self.process_ops.cancel(identity, reason)
        else: q = Quiescence(False, 'writer authority not established', time.time())
        if not isinstance(q, Quiescence) or (q.confirmed and not q.evidence): raise ValueError('invalid quiescence evidence')
        if fence:
            return self._persist_fenced(key, q, fenced_revision)
        # OS observation can overlap a worker evidence write. Retry only the
        # persistence, against fresh records with the same exact process/owner.
        process, writer = r.process, r.writer
        for _ in range(STATE_CAS_ATTEMPTS):
            r = self.store.get(key)
            if r.process != process or r.writer != writer:
                raise StateConflict('observation binding changed')
            prior = containment = (r.receipt or {}).get('containment')
            if prior and q.details:
                containment = merge_evidence(prior, q.details)
                r.receipt = dict(r.receipt, containment=containment)
                if containment['inventory_complete'] is False:
                    q = Quiescence(False, 'retained containment incomplete', q.observed_at, containment)
            if not q.confirmed:
                q = self._reprove_stale(r, containment) or q
            r.quiescence = asdict(q)
            if not q.confirmed:
                r.state = 'unresolved'
            try:
                self.store.compare_and_swap(key, r.revision, r)
                return q
            except StateConflict:
                continue
        raise StateConflict('observation persistence contended')
    def _persist_fenced(self, key, q, fenced_revision):
        """Strict proof: one CAS on the revision observed before the OS proof."""
        r = self.store.get(key)
        if r.revision != fenced_revision:
            raise StateConflict('proof revision changed')
        prior = (r.receipt or {}).get('containment')
        if prior and q.details:
            r.receipt = dict(r.receipt, containment=merge_evidence(prior, q.details))
        if q.details and not q.confirmed:
            raise StateConflict('fenced proof unconfirmed')
        r.quiescence = asdict(q)
        if not q.confirmed:
            r.state = 'unresolved'
        try:
            self.store.compare_and_swap(key, r.revision, r)
        except StateConflict:
            raise StateConflict('proof revision changed') from None
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
        for _ in range(STATE_CAS_ATTEMPTS):
            try:
                confirmed = self.reconcile(key).confirmed
            except StateConflict:
                # A strict proof is never retried or settled as an unresolved outcome.
                if getattr(self.process_ops, 'strict_revision_fence', False):
                    raise
                confirmed = False
            r = self.store.get(key)
            if r.outcome is not None:
                return r
            outcome['quiescent'] = confirmed
            if confirmed:
                r.outcome, r.pending_outcome = outcome, None
                r.finished_at = time.time()
            else:
                r.pending_outcome = outcome
            r.state = 'settling' if confirmed else 'unresolved'
            try:
                return self.store.compare_and_swap(key, r.revision, r)
            except StateConflict:
                continue
        # The reservation remains held. The caller can retry reconciliation;
        # no launch or success is inferred from persistence contention.
        return self.store.get(key)
