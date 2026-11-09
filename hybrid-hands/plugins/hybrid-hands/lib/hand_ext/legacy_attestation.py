"""Explicit operator exception; never signal, infer OS births, or certify quiescence."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict

from . import parallel
from .execution_admission import AdmissionController, Reservation
from .execution_state import ExecutionRecord, ExecutionStore, StateConflict, _plain, atomic_json
from .execution_supervisor import ExecutionSupervisor, Quiescence
from .post_hoc_reverify import bindings
from .process_containment import ProcessTable, Descendants

METHOD = 'operator_legacy_attest'


class LegacyOwnerAlive(StateConflict):
    """Safe public instruction without arbitrary OS/transport error text."""


def latest_locked(store: ExecutionStore, r: ExecutionRecord) -> None:
    for path in store.root.glob('*.json'):
        other = store._read(path)
        if (other.key.invocation_id == r.key.invocation_id
                and other.key != r.key and other.key.epoch >= r.key.epoch):
            raise StateConflict('latest exact epoch required')


def legacy_bindings(r: ExecutionRecord, saved: dict) -> None:
    if saved.get('binding'):
        if saved['binding'] != bindings(r):
            raise StateConflict('immutable legacy containment binding required')
    # Older workers did not retain containment. Require the durable public
    # dispatch receipt to independently pin every available placement/request.
    from .paseo_recovery import consistent_bindings
    t = (r.receipt or {}).get('transport', {})
    consistent_bindings(r, t)
    from .paseo_controller import valid_completion_binding
    receipt = r.receipt or {}
    controller = receipt.get('controller', {})
    context = receipt.get('completion', {}).get('context', {})
    if (not valid_completion_binding(r)
            or context.get('worktree') != r.invocation.isolated_cwd
            or controller.get('policy_root') != r.invocation.source_cwd
            or controller.get('backend') != r.invocation.backend
            or not r.writer or r.writer.get('owner_id') != receipt.get('worker_owner')
            or t.get('gatewayEnv') != dict(HYBRID_HANDS_INVOCATION_ID=r.key.invocation_id,
                HYBRID_HANDS_EXECUTION_ROOT=(r.reservation or {}).get('store_root'))):
        raise StateConflict('durable legacy authority binding required')
    fields = {'targetKey':'target_key', 'projectId':'project_id',
              'workspaceId':'workspace_id', 'agentId':'agent_id'}
    if (any(t.get(k) != getattr(r.attempt, f) or not t.get(k) for k, f in fields.items())
            or t.get('requestKey') != r.attempt.request_key
            or t.get('messageId') != r.attempt.request_key
            or t.get('cwd') != r.invocation.isolated_cwd
            or t.get('parentAgentId') != r.invocation.parent_paseo_agent_id
            or t.get('sendConfirmed') is not True):
        raise StateConflict('exact legacy dispatch receipt required')


def reservation_bound(r: ExecutionRecord, value: dict) -> bool:
    reservation = Reservation.from_dict(value)
    canonical = hashlib.sha256(json.dumps(_plain(r.key), sort_keys=True).encode()).hexdigest()
    return (reservation.key == r.key and reservation.reservation_id == canonical
            and reservation.scope_id == r.invocation.scope_id
            and bool(reservation.store_root))


def never_admitted(store: ExecutionStore, r: ExecutionRecord, *, terminal: bool = False) -> None:
    """Pool absence matters even when reservation-before-CAS left a bare intent."""
    if terminal and (not r.outcome or r.outcome.get('status') != 'not_admitted'
                     or r.outcome.get('backend_exit_code') != 8):
        raise StateConflict('not-admitted terminal evidence required')
    if (r.state != ('not_admitted' if terminal else 'intent')
            or r.reservation is not None or r.process is not None or r.writer is not None
            or (r.outcome is not None and not terminal)
            or r.pending_outcome is not None or r.started_at is not None
            or (r.finished_at is not None and not terminal) or r.artifacts
            or r.settle_keys or r.quiescence is not None
            or set(r.receipt or {}) - ({'controller', 'completion', 'brief_digest'}
                | ({'never_admitted_attestation'} if terminal else set()))
            or any(getattr(r.attempt, f) is not None for f in
                   ('target_key', 'project_id', 'workspace_id', 'agent_id', 'thread_id'))):
        raise StateConflict('never-admitted proof unavailable')
    try:
        pool = list(parallel.durable_reservations())
    except (OSError, ValueError):
        raise StateConflict('pool authority unavailable') from None
    for _, data in pool:
        other = Reservation.from_dict(data)
        if other.key == r.key:
            raise StateConflict('durable reservation evidence present')


def binding_digest(r: ExecutionRecord, reservation: dict | None) -> str:
    bound = bindings(r)
    bound['reservation'] = reservation
    bound['writer_owner'] = (r.writer or {}).get('owner_id')
    receipt = r.receipt or {}
    bound['receipt'] = {k: receipt.get(k) for k in
                        ('controller', 'completion', 'transport', 'worker_run_dir')}
    return hashlib.sha256(json.dumps(bound, sort_keys=True).encode()).hexdigest()


def harmless_diagnostics(values) -> bool:
    if not isinstance(values, list):
        return False
    return all(isinstance(d, dict)
               and set(d) <= {'method', 'stage', 'error', 'resolution', 'pid', 'start'}
               and d.get('method') == 'root_group+tracked_tree+env_marker'
               and d.get('stage') == 'marker'
               and (d.get('error') == 'exit_or_reused'
                    or (d.get('error') == 'einval'
                        and d.get('resolution') == 'gone_or_reused'))
               for d in values)


def attested(r: ExecutionRecord) -> bool:
    q = r.quiescence or {}
    proof = (r.receipt or {}).get('legacy_attestation') or {}
    try:
        reservation = r.reservation if r.reservation is not None else proof.get('reservation')
        evidence = proof.get('evidence')
        if (not isinstance(evidence, dict) or evidence != q.get('details')
                or set(evidence) != {'method', 'attested', 'owner', 'root', 'group',
                                     'marker_matches', 'authoritative', 'diagnostics'}):
            return False
        def absent(value, pid):
            return (isinstance(value, dict)
                    and set(value) == ({'pid', 'start', 'observation', 'observed_start'}
                                       if value.get('observation') == 'reused'
                                       else {'pid', 'start', 'observation'})
                    and (value.get('start') is None or isinstance(value.get('start'), str))
                    and type(pid) is int and pid > 0
                    and value.get('pid') == pid
                    and (value.get('observation') == 'absent'
                         or (value.get('observation') == 'reused'
                             and isinstance(value.get('start'), str) and bool(value['start'])
                             and isinstance(value.get('observed_start'), str)
                             and bool(value['observed_start'])
                             and value['start'] != value['observed_start'])))
        return (q.get('confirmed') is False and q.get('evidence') == METHOD
                and evidence.get('method') == METHOD and evidence.get('attested') is True
                and evidence.get('group') == 'absent'
                and type(evidence.get('marker_matches')) is int and evidence['marker_matches'] == 0
                and evidence.get('authoritative') is True and harmless_diagnostics(evidence.get('diagnostics'))
                and absent(evidence.get('owner'), int(r.process['supervisor_id']))
                and absent(evidence.get('root'), r.process['pid'])
                and proof.get('reservation') == reservation
                and reservation_bound(r, reservation)
                and proof.get('binding_digest') == binding_digest(r, reservation)
                and isinstance(proof.get('reason'), str) and bool(proof['reason'].strip())
                and r.outcome is not None and r.outcome.get('status') == 'cancelled')
    except (TypeError, ValueError, KeyError, AttributeError, StateConflict):
        return False


def settlement_authorized(supervisor: ExecutionSupervisor, key) -> bool:
    if not hasattr(supervisor, 'store'):
        return supervisor.reconcile(key).confirmed
    r = supervisor.store.get(key)
    if attested(r):
        proof = r.receipt['legacy_attestation']
        reservation = r.reservation or proof['reservation']
        return reservation['store_root'] == str(supervisor.store.root)
    return supervisor.reconcile(key).confirmed


def _absent(table: ProcessTable, pid: int, retained: dict | None,
            supplied: str | None, label: str) -> dict:
    if type(pid) is not int or pid <= 0:
        raise StateConflict('exact OS pid required')
    if isinstance(retained, dict) and retained.get('pid') != pid:
        raise StateConflict('retained OS pid mismatch')
    birth = retained.get('start') if isinstance(retained, dict) else None
    if birth and supplied and supplied != birth:
        raise StateConflict('operator OS birth conflicts with retained identity')
    birth = birth or supplied
    if birth is not None and (not isinstance(birth, str) or not birth):
        raise StateConflict('valid OS birth evidence required')
    current = table.identity(pid)
    if current is None:
        return dict(pid=pid, observation='absent', start=birth)
    if not birth or current.start == birth:
        if label == 'owner':
            raise LegacyOwnerAlive('close exact child through public Paseo')
        raise StateConflict('root/group still present or identity uncertain')
    return dict(pid=pid, start=birth, observation='reused', observed_start=current.start)


def _proof(store: ExecutionStore, r: ExecutionRecord, table: ProcessTable,
           owner_start: str | None, root_start: str | None) -> dict:
    saved = (r.receipt or {}).get('containment', {})
    modern_fields = {'inventory', 'inventory_complete', 'root_reaped', 'first_fatal'}
    if (not isinstance(saved, dict) or set(saved) - {'binding'}
            or modern_fields.intersection((r.quiescence or {}).get('details', {}))):
        raise StateConflict('retained containment must use post_hoc_reverify')
    legacy_bindings(r, saved)
    if (r.state != 'unresolved' or not r.process or not r.reservation
            or not (r.receipt or {}).get('worker_owner')
            or not (r.receipt or {}).get('completion')
            or not (r.receipt or {}).get('worker_run_dir')
            or (r.pending_outcome or r.outcome or {}).get('status') != 'cancelled'
            or (r.pending_outcome and r.outcome and r.pending_outcome != r.outcome)
            or not all(getattr(r.attempt, f) for f in
                       ('request_key', 'target_key', 'project_id', 'workspace_id', 'agent_id'))):
        raise StateConflict('legacy cancelled authority required')
    reservation = Reservation.from_dict(r.reservation)
    if (not reservation_bound(r, r.reservation) or reservation.scope_id != r.invocation.scope_id
            or reservation.store_root != str(store.root)):
        raise StateConflict('reservation binding mismatch')
    path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
    try:
        if json.loads(path.read_text()) != _plain(reservation):
            raise StateConflict('pool reservation mismatch')
        owner_pid = int(r.process['supervisor_id'])
        owner = _absent(table, owner_pid, saved.get('owner'), owner_start, 'owner')
        root = _absent(table, r.process['pid'], saved.get('root'), root_start, 'root')
        # Numeric group IDs are only probed, never signalled. A reused leader
        # requires explicit birth proof, and a live group is still refused.
        if table.group_present(r.process['pgid']):
            raise StateConflict('root/group still present')
        rows = table.snapshot()
        tree = object.__new__(Descendants)
        tree.table, tree.invocation = table, r.key.invocation_id
        tree.authoritative, tree.diagnostics, tree.inventory_complete = True, [], True
        for item in rows.values():
            if item.uid == os.getuid() and not item.zombie:
                if tree.marker(item) or not tree.authoritative:
                    raise StateConflict('marker scan not clean')
    except StateConflict:
        raise
    except Exception:
        raise StateConflict('legacy OS proof unavailable') from None
    with store.locked():
        latest_locked(store, r)
        if store._read(store._path(r.key)).revision != r.revision:
            raise StateConflict('proof revision changed')
    return dict(method=METHOD, attested=True, owner=owner, root=root,
                group='absent', marker_matches=0, authoritative=tree.authoritative,
                diagnostics=tree.diagnostics)


class AttestationSupervisor(ExecutionSupervisor):
    def reconcile(self, key):
        r = self.store.get(key)
        if not attested(r):
            raise StateConflict('exact operator attestation required')
        return Quiescence(**r.quiescence)


def recover_legacy(store: ExecutionStore, r: ExecutionRecord, *, apply: bool,
                   reason: str | None, table: ProcessTable | None = None,
                   owner_start: str | None = None, root_start: str | None = None) -> ExecutionRecord:
    if not isinstance(reason, str) or not reason.strip():
        raise StateConflict('explicit operator reason required')
    # The reason is operator-owned text, never constructed from exceptions/env.
    reason = reason.strip()
    with parallel.pool_lock():
        if r.state == 'not_admitted':
            never_admitted(store, r, terminal=True)
            return r
        if r.state == 'intent':
            never_admitted(store, r)
            if not apply:
                return r
            with store.locked():
                current = store._read(store._path(r.key))
                latest_locked(store, current)
                if current.to_dict() != r.to_dict():
                    raise StateConflict('proof revision changed')
                never_admitted(store, current)
                current.receipt = dict(current.receipt or {}, never_admitted_attestation=dict(
                    reason=reason, key=_plain(current.key)))
                current.state = 'not_admitted'
                current.outcome = dict(status='not_admitted', backend_exit_code=8,
                                       reason='operator_never_admitted')
                current.finished_at = time.time(); current.revision += 1
                atomic_json(store._path(r.key), current.to_dict())
            return current
        if attested(r):
            reservation = r.reservation or r.receipt['legacy_attestation']['reservation']
            if reservation['store_root'] != str(store.root):
                raise StateConflict('reservation store mismatch')
            if r.receipt['legacy_attestation']['reason'] != reason:
                raise StateConflict('attestation reason mismatch')
            if r.reservation:
                reservation = Reservation.from_dict(r.reservation)
                path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
                try:
                    if json.loads(path.read_text()) != _plain(reservation):
                        raise StateConflict('pool reservation mismatch')
                except (OSError, ValueError):
                    raise StateConflict('pool reservation unavailable') from None
            if not apply:
                return r
            if r.state == 'awaiting_review' and not r.reservation:
                reservation = Reservation.from_dict(r.receipt['legacy_attestation']['reservation'])
                path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
                if path.exists():
                    if json.loads(path.read_text()) != _plain(reservation):
                        raise StateConflict('pool reservation mismatch')
                    path.unlink()
                    fd = os.open(path.parent, os.O_RDONLY)
                    try: os.fsync(fd)
                    finally: os.close(fd)
                return r
        else:
            table = table or ProcessTable()
            _proof(store, r, table, owner_start, root_start)
            if not apply:
                return r
            # Fresh proof immediately before one strict CAS. A scan racing a
            # durable write cannot be retried with a newer revision.
            details = _proof(store, r, table, owner_start, root_start)
            current = store.get(r.key)
            if current.to_dict() != r.to_dict():
                raise StateConflict('proof revision changed')
            current.receipt = dict(current.receipt, legacy_attestation=dict(
                binding_digest=binding_digest(r, r.reservation),
                reservation=r.reservation, reason=reason, evidence=details))
            current.quiescence = asdict(Quiescence(False, METHOD, time.time(), details))
            current.outcome = dict(current.pending_outcome or current.outcome,
                                   quiescent=True)
            current.pending_outcome = None
            current.state = 'settling'; current.finished_at = current.finished_at or time.time()
            # Legacy settled outcomes can only gain explicit authority under the
            # locked strict revision fence; normal outcome immutability remains.
            with store.locked():
                old = store._read(store._path(r.key))
                latest_locked(store, old)
                if old.to_dict() != r.to_dict():
                    raise StateConflict('proof revision changed')
                current.revision += 1
                atomic_json(store._path(r.key), current.to_dict())
    from .execution_worker import ExecutionWorker
    from .paseo_completion import CompletionService
    supervisor = AttestationSupervisor(store)
    admission = AdmissionController(store, supervisor, None)
    worker = ExecutionWorker(store, supervisor)
    completion = CompletionService(store, supervisor, admission).attach(worker)
    completion.reconcile(r.key)
    return store.get(r.key)
