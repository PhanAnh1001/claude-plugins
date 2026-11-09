"""Read-only OS proof for cancelled attempts. Never reconstruct launch authority."""
from dataclasses import asdict
import json
import os
import time

from .execution_state import StateConflict, _plain
from .execution_supervisor import Quiescence, ExecutionSupervisor
from .process_containment import OSIdentity, ProcessTable, Descendants
from .execution_admission import AdmissionController, Reservation
from . import parallel

METHOD = 'post_hoc_reverify'


def bindings(record):
    return dict(invocation=_plain(record.invocation), attempt=_plain(record.attempt),
                process=record.process, worker_owner=(record.receipt or {}).get('worker_owner'),
                reservation=record.reservation)


def identity(value):
    if (not isinstance(value, dict) or type(value.get('pid')) is not int
            or value['pid'] <= 0 or not isinstance(value.get('start'), str)
            or not value['start'] or type(value.get('uid')) is not int):
        raise StateConflict('durable OS identity required')
    return OSIdentity(**value)


class ReverifyOps:
    """Every supervisor observation repeats the proof; never signals or launches."""
    # The supervisor CASes the exact revision observed before this proof.
    strict_revision_fence = True

    def __init__(self, store, record, table=None):
        self.store, self.key = store, record.key
        self.table = table or ProcessTable()
        self.saved = (record.receipt or {}).get('containment', {})
        self.bound = self.saved.get('binding')
        self.first_revision = record.revision

    def reconcile(self, process):
        r = self.store.get(self.key)
        if self.first_revision is not None and r.revision != self.first_revision:
            raise StateConflict('proof revision changed')
        if (not self.bound or self.saved.get('inventory_complete') is not True
                or self.saved.get('root_reaped') is not True):
            raise StateConflict('complete retained containment evidence required')
        bound = bindings(r)
        # Standard settlement clears the reservation only after the final proof.
        if bound != self.bound:
            raise StateConflict('containment binding mismatch')
        if not all(getattr(r.attempt, f) for f in
                   ('request_key', 'target_key', 'project_id', 'workspace_id', 'agent_id')):
            raise StateConflict('exact placement required')
        if not r.process or not (r.receipt or {}).get('worker_owner'):
            raise StateConflict('worker identity required')
        if asdict(process) != {k: r.process[k] for k in ('pid', 'pgid', 'start_identity')}:
            raise StateConflict('process binding mismatch')
        pending = r.pending_outcome or r.outcome
        if not pending or pending.get('status') != 'cancelled':
            raise StateConflict('cancelled outcome required')
        root, owner = identity(self.saved.get('root')), identity(self.saved.get('owner'))
        if str(owner.pid) != r.process.get('supervisor_id'):
            raise StateConflict('owner OS identity not pinned to supervisor')
        inventory = [identity(i) for i in self.saved.get('inventory', [])]
        if root.pid != process.pid or not any(root.matches(i) for i in inventory):
            raise StateConflict('root inventory required')
        query = getattr(self.table, 'identity', None)
        if query is None:
            raise StateConflict('direct OS identity query required')
        try:
            for item in inventory:
                current = query(item.pid)
                if item.matches(current):
                    raise StateConflict('tracked identity still present')
            ack = dict(worker_owner=r.receipt['worker_owner'], key=_plain(r.key))
            if self.saved.get('owner_done') != ack and owner.matches(query(owner.pid)):
                raise StateConflict('worker owner still executing')
            # Snapshot errors are never treated as an empty table.
            rows = self.table.snapshot()
            protected = [identity(i) for i in self.saved.get('protected', [])]
            if not any(owner.matches(i) for i in protected):
                raise StateConflict('exact protected owner required')
            tree = object.__new__(Descendants)
            tree.table, tree.invocation = self.table, r.key.invocation_id
            tree.authoritative, tree.diagnostics = True, []
            tree.inventory_complete = True
            for item in rows.values():
                if item.uid != os.getuid() or item.zombie:
                    continue
                if any(item.matches(i) for i in protected):
                    continue
                if tree.marker(item) or not tree.authoritative:
                    raise StateConflict('marker scan not clean')
        except StateConflict:
            raise
        except Exception:
            raise StateConflict('OS proof unavailable') from None
        if self.store.get(self.key).revision != r.revision:
            raise StateConflict('proof revision changed')
        self.first_revision = None
        return Quiescence(True, METHOD, time.time(), dict(method=METHOD,
                          root=asdict(root), root_reaped=True,
                          owner=asdict(owner), inventory=[asdict(i) for i in inventory],
                          inventory_complete=True, diagnostics=tree.diagnostics))

    def cancel(self, process, reason):
        return self.reconcile(process)


def recover_cancelled(store, record, *, apply=False, table=None):
    from .execution_supervisor import ProcessIdentity
    from .execution_worker import ExecutionWorker
    from .paseo_completion import CompletionService
    if record.pending_outcome is not None and record.state != 'unresolved':
        raise StateConflict('cancelled unresolved state required')
    if (record.outcome is not None and record.pending_outcome is not None
            and record.outcome != record.pending_outcome):
        raise StateConflict('conflicting pending outcome')
    if (record.outcome is not None and record.outcome.get('status') != 'cancelled'):
        raise StateConflict('conflicting settled outcome')
    if record.state == 'awaiting_review' and not record.reservation:
        if (record.quiescence or {}).get('evidence') != METHOD:
            raise StateConflict('post-hoc proof required')
        return record
    if not record.process or not record.reservation:
        raise StateConflict('cancelled writer reservation required')
    reservation = Reservation.from_dict(record.reservation)
    if (reservation.key != record.key or reservation.store_root != str(store.root)
            or reservation.scope_id != record.invocation.scope_id):
        raise StateConflict('reservation binding mismatch')
    path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
    try:
        if json.loads(path.read_text()) != _plain(reservation):
            raise StateConflict('pool reservation mismatch')
    except (OSError, ValueError):
        raise StateConflict('pool reservation unavailable') from None
    if not (record.receipt or {}).get('completion'):
        raise StateConflict('standard completion binding required')
    ops = ReverifyOps(store, record, table)
    process = ProcessIdentity(**{k:record.process[k] for k in ('pid', 'pgid', 'start_identity')})
    ops.reconcile(process)
    if not apply:
        return record
    # Recheck revision inside the standard supervisor's CAS observation.
    ops.first_revision = record.revision
    supervisor = ExecutionSupervisor(store, ops)
    admission = AdmissionController(store, supervisor, None)
    worker = ExecutionWorker(store, supervisor)
    # Worker wrapping is unnecessary here; only the read-only proof has authority.
    supervisor.process_ops = ops
    completion = CompletionService(store, supervisor, admission).attach(worker)
    worker.reconcile(record.key)
    if store.get(record.key).reservation:
        completion.reconcile(record.key)
    return store.get(record.key)
