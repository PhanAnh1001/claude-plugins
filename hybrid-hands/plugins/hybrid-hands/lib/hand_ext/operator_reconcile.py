"""Operator settlement for a dead writer whose retained containment stays incomplete.

The automatic supervisor keeps failing closed on sticky historical uncertainty
(``merge_evidence`` never forgets ``inventory_complete=False``). This explicit,
read-only proof lets an operator settle such an execution only when every
writer identity is provably gone, then releases through the official
CompletionService -> AdmissionController.release path. It never signals.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from . import parallel
from .execution_admission import AdmissionController, Reservation
from .execution_state import ExecutionRecord, ExecutionStore, StateConflict, _plain, atomic_json
from .execution_supervisor import ExecutionSupervisor, Quiescence
from .post_hoc_reverify import bindings
from .process_containment import Descendants, OSIdentity, ProcessTable

METHOD = 'operator_reconcile'
# Exact evidence string the supervisor persists for sticky incomplete containment.
STICKY_EVIDENCE = 'retained containment incomplete'
# Paseo agent status that proves the gateway child is terminal.
TERMINAL_AGENT_STATUS = 'closed'
AGENT_PROBE_COMMAND = 'agent-terminal'
NO_TRANSPORT = 'none'


@dataclass
class ReconcilePlan:
    """Dry-run verdict; ``blocked`` holds the first failed check."""
    eligible: bool
    blocked: str | None
    evidence: dict = field(default_factory=dict)
    record: ExecutionRecord | None = None

    def summary(self) -> dict:
        return dict(method=METHOD, eligible=self.eligible, blocked=self.blocked,
                    evidence=self.evidence)


def operator_reconciled(r: ExecutionRecord) -> bool:
    """Strict check that the record carries this module's own settlement."""
    q = r.quiescence or {}
    proof = (r.receipt or {}).get(METHOD) or {}
    reason = proof.get('reason')
    return (q.get('confirmed') is True and q.get('evidence') == METHOD
            and isinstance(reason, str) and bool(reason.strip())
            and q.get('details') == proof.get('evidence')
            and r.outcome is not None and r.outcome.get('provenance') == METHOD
            and r.outcome.get('quiescent') is True)


def applicable(r: ExecutionRecord) -> bool:
    if operator_reconciled(r):
        return True
    return (r.state == 'unresolved' and r.outcome is None
            and (r.quiescence or {}).get('evidence') == STICKY_EVIDENCE)


def _identity(value) -> OSIdentity:
    try:
        item = OSIdentity(**value)
    except (TypeError, ValueError):
        raise StateConflict('durable OS identity required') from None
    if type(item.pid) is not int or item.pid <= 0 or not isinstance(item.start, str) or not item.start:
        raise StateConflict('durable OS identity required')
    return item


def _gone(table: ProcessTable, pid, start) -> str:
    """'absent' or 'reused'; a missing birth is accepted only when fully absent."""
    if type(pid) is not int or pid <= 0:
        raise StateConflict('exact OS pid required')
    current = table.identity(pid)
    if current is None:
        return 'absent'
    if isinstance(start, str) and start and current.start != start:
        return 'reused'
    raise StateConflict(f'tracked identity still present: {pid}')


def _check_entry(store: ExecutionStore, r: ExecutionRecord) -> dict:
    saved = (r.receipt or {}).get('containment')
    if (r.state != 'unresolved' or r.outcome is not None or not isinstance(r.pending_outcome, dict)
            or not r.process or not r.reservation or not isinstance(saved, dict)):
        raise StateConflict('unresolved pending writer reservation required')
    if (r.quiescence or {}).get('evidence') != STICKY_EVIDENCE or saved.get('inventory_complete') is not False:
        raise StateConflict('sticky incomplete containment required')
    if not saved.get('binding') or saved['binding'] != bindings(r):
        raise StateConflict('containment binding mismatch')
    if saved.get('root_reaped') is not True:
        raise StateConflict('root reap required')
    reservation = Reservation.from_dict(r.reservation)
    if (reservation.key != r.key or reservation.store_root != str(store.root)
            or reservation.scope_id != r.invocation.scope_id):
        raise StateConflict('reservation binding mismatch')
    path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
    try:
        if json.loads(path.read_text()) != _plain(reservation):
            raise StateConflict('pool reservation mismatch')
    except (OSError, ValueError):
        raise StateConflict('pool reservation unavailable') from None
    return saved


def _check_processes(r: ExecutionRecord, saved: dict, table: ProcessTable) -> dict:
    root, owner = _identity(saved.get('root')), _identity(saved.get('owner'))
    if root.pid != r.process['pid'] or str(owner.pid) != str(r.process.get('supervisor_id')):
        raise StateConflict('root/owner identity not pinned to process')
    evidence = dict(owner=_gone(table, owner.pid, owner.start), root=_gone(table, root.pid, root.start))
    if table.group_present(r.process['pgid']):
        raise StateConflict('process group still present')
    tracked = list(saved.get('inventory') or []) + list(saved.get('diagnostics') or [])
    if saved.get('first_fatal'):
        tracked.append(saved['first_fatal'])
    for item in tracked:
        if not isinstance(item, dict) or 'pid' not in item:
            continue  # stage-only diagnostics carry no process identity
        _gone(table, item['pid'], item.get('start'))
    evidence.update(group='absent', tracked=len(tracked))
    return evidence


def _scan_markers(r: ExecutionRecord, table: ProcessTable) -> dict:
    """Whole same-uid scan; an unreadable live environment blocks (never 'clean')."""
    rows = table.snapshot()  # errors propagate: a failed snapshot is never empty
    tree = object.__new__(Descendants)
    tree.table, tree.invocation = table, r.key.invocation_id
    tree.authoritative, tree.diagnostics, tree.inventory_complete = True, [], True
    scanned = 0
    for item in rows.values():
        # Same rule as post_hoc_reverify: zombies cannot write.
        if item.uid != os.getuid() or item.zombie:
            continue
        scanned += 1
        if tree.marker(item):
            raise StateConflict('execution marker still present')
        if not tree.authoritative:
            raise StateConflict('marker scan not authoritative')
    return dict(scanned=scanned, marker_matches=0, scan_diagnostics=len(tree.diagnostics))


# Bridge `agent-terminal` outcomes: label equals the recorded parent, or label is missing
# (archived agents lose labels). A present-but-wrong label fails in the bridge itself.
PARENT_LABEL_STATES = frozenset({'match', 'absent'})


def _check_agent(r: ExecutionRecord, probe: Callable[[dict], dict] | None, target) -> dict:
    transport = (r.receipt or {}).get('transport')
    if not transport and not r.attempt.agent_id:
        return dict(transport=NO_TRANSPORT)
    if probe is None:
        raise StateConflict('agent status probe unavailable')
    request = dict(command=AGENT_PROBE_COMMAND, targetKey=r.attempt.target_key, target=target,
                   agentId=r.attempt.agent_id, workspaceId=r.attempt.workspace_id,
                   parentAgentId=r.invocation.parent_paseo_agent_id)
    try:
        proof = probe(request)
    except Exception:
        raise StateConflict('exact agent status unavailable') from None
    if (not isinstance(proof, dict) or proof.get('ok') is not True
            or proof.get('targetKey') != r.attempt.target_key
            or proof.get('agentId') != r.attempt.agent_id
            or proof.get('workspaceId') != r.attempt.workspace_id
            or proof.get('parentLabel') not in PARENT_LABEL_STATES):
        raise StateConflict('exact agent status unavailable')
    if proof.get('status') != TERMINAL_AGENT_STATUS:
        raise StateConflict('agent not closed')
    return dict(transport='paseo', agent_status=proof['status'], agent_archived=proof.get('archived') is True,
                parent_label=proof['parentLabel'])


def prove(store, r, *, table, probe, target) -> dict:
    saved = _check_entry(store, r)
    evidence = dict(method=METHOD, root_reaped=True)
    try:
        evidence.update(_check_processes(r, saved, table))
        evidence.update(_scan_markers(r, table))
    except StateConflict:
        raise
    except Exception:
        raise StateConflict('OS proof unavailable') from None
    evidence.update(_check_agent(r, probe, target))
    return evidence


class OperatorSupervisor(ExecutionSupervisor):
    """Only replays this module's durable settlement; never observes the OS."""
    def reconcile(self, key):
        r = self.store.get(key)
        if not operator_reconciled(r):
            raise StateConflict('operator reconcile required')
        return Quiescence(**r.quiescence)

    def cancel(self, key, reason):
        return self.reconcile(key)


def _completion(store):
    from .execution_worker import ExecutionWorker
    from .paseo_completion import CompletionService
    supervisor = OperatorSupervisor(store)
    worker = ExecutionWorker(store, supervisor)
    return CompletionService(store, supervisor, AdmissionController(store, supervisor, None)).attach(worker)


def _release(store, key, completion_factory) -> None:
    completion = (completion_factory or _completion)(store)
    completion.worker.reconcile(key)  # runs settlement sinks, then official release
    if store.get(key).reservation:
        completion.reconcile(key)


def _settle(store, r, evidence, reason, clock) -> None:
    from .legacy_attestation import latest_locked
    with store.locked():
        current = store._read(store._path(r.key))
        latest_locked(store, current)
        if current.to_dict() != r.to_dict():
            raise StateConflict('proof revision changed')
        at = clock()
        current.receipt = dict(current.receipt, **{METHOD: dict(
            reason=reason, evidence=evidence, at=at, prior_revision=r.revision)})
        current.quiescence = asdict(Quiescence(True, METHOD, at, evidence))
        current.outcome = dict(current.pending_outcome, quiescent=True, provenance=METHOD)
        current.pending_outcome = None
        current.state = 'settling'
        current.finished_at = current.finished_at or at
        current.revision += 1
        atomic_json(store._path(r.key), current.to_dict())


def recover_unresolved(store: ExecutionStore, r: ExecutionRecord, *, apply: bool = False,
                       reason: str | None = None, table: ProcessTable | None = None,
                       probe: Callable[[dict], dict] | None = None, target=None,
                       clock: Callable[[], float] = time.time,
                       completion_factory=None):
    """Dry-run returns ReconcilePlan; apply settles, releases and returns the record."""
    if apply and (not isinstance(reason, str) or not reason.strip()):
        raise StateConflict('explicit operator reason required')
    if operator_reconciled(r):
        if apply and r.reservation:
            _release(store, r.key, completion_factory)
            return store.get(r.key)
        return r if apply else ReconcilePlan(True, None, (r.quiescence or {}).get('details', {}), r)
    table = table or ProcessTable()
    try:
        evidence = prove(store, r, table=table, probe=probe, target=target)
    except StateConflict as exc:
        if apply:
            raise
        return ReconcilePlan(False, str(exc), {}, r)
    if not apply:
        return ReconcilePlan(True, None, evidence, r)
    # Fresh proof immediately before the single locked revision-fenced write.
    evidence = prove(store, r, table=table, probe=probe, target=target)
    _settle(store, r, evidence, reason.strip(), clock)
    _release(store, r.key, completion_factory)
    return store.get(r.key)
