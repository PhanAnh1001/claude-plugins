"""Fail closed, offline proof and atomic settlement for never-dispatched attempts."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import time

from . import parallel
from .execution_admission import AdmissionController, Reservation
from .execution_state import StateConflict, atomic_json
from .paseo_transport import trusted_schema_rejection


def consistent_bindings(record, transport):
    """Compare receipt claims to immutable bindings without filling legacy gaps."""
    fields = {'workspaceId': 'workspace_id', 'targetKey': 'target_key',
              'projectId': 'project_id', 'agentId': 'agent_id'}
    for public, field in fields.items():
        bound = getattr(record.attempt, field)
        if bound is not None and public in transport and transport[public] != bound:
            raise StateConflict('transport binding mismatch')
    paths = {'cwd': record.invocation.isolated_cwd,
             'sourceCwd': record.invocation.source_cwd}
    for public, bound in paths.items():
        if public not in transport:
            continue
        claimed = transport[public]
        if not isinstance(claimed, str) or not claimed or not bound:
            raise StateConflict('transport cwd binding mismatch')
        if Path(claimed).resolve() != Path(bound).resolve():
            raise StateConflict('transport cwd binding mismatch')


def untouched(record, *, recovery=False):
    receipt = record.receipt or {}
    if set(receipt) - {'controller', 'completion', 'transport'} or record.settle_keys:
        raise StateConflict('other dispatch evidence present')
    t = receipt.get('transport', {})
    if (record.state != 'admitted' or not record.reservation or record.writer is not None
            or record.process is not None or record.outcome is not None
            or record.pending_outcome is not None or record.started_at is not None
            or record.finished_at is not None or record.artifacts):
        raise StateConflict('dispatch authority uncertain')
    forbidden = ('cancelPending', 'cancelConfirmed', 'archiveConfirmed', 'reopenConfirmed')
    allowed_pending = (None, 'workspace', 'create') if recovery else (None, 'workspace')
    if any(k in t for k in forbidden) or t.get('sendConfirmed') or t.get('pending') not in allowed_pending:
        raise StateConflict('dispatch evidence present')
    known = {'pending', 'workspaceConfirmed', 'agentKey', 'createConfirmed', 'targetKey',
             'projectId', 'workspaceId', 'agentId', 'workspaceKey', 'parentAgentId', 'cwd',
             'sourceCwd', 'providerId', 'revision', 'requestKey', 'admitted', 'expectedProviderId', 'model',
             'effort', 'gatewayEnv', 'quiescent', 'freshDispatch', 'reviewed'}
    if recovery and set(t) - known:
        raise StateConflict('unknown transport evidence')
    if recovery:
        consistent_bindings(record, t)
        creating = t.get('pending') == 'create'
        dispatched = ('sendConfirmed', 'messageId', 'briefDigest',
                      'createConfirmed')
        if not creating:
            dispatched += ('agentKey', 'providerId')
        if any(field in t for field in dispatched):
            raise StateConflict('dispatch evidence present')
    if recovery and t.get('pending') == 'create':
        if t.get('workspaceConfirmed') is not True or not isinstance(t.get('agentKey'), str) or not t['agentKey']:
            raise StateConflict('create recovery not applicable')
        for public, field in {'targetKey': 'target_key', 'workspaceId': 'workspace_id',
                              'projectId': 'project_id', 'agentId': 'agent_id'}.items():
            if not getattr(record.attempt, field) or t.get(public) != getattr(record.attempt, field):
                raise StateConflict('exact create binding required')
        if t.get('parentAgentId') != record.invocation.parent_paseo_agent_id:
            raise StateConflict('parent binding mismatch')
        return t
    if recovery and (t.get('messageId') or t.get('briefDigest') or t.get('pending') != 'workspace' or t.get('workspaceConfirmed')
                     or t.get('agentKey') or t.get('createConfirmed')):
        raise StateConflict('workspace recovery not applicable')
    return t


class PreDispatchAdmission(AdmissionController):
    """Separate authority from process quiescence: no process ever existed."""
    def fail(self, key, proof, reason, *, recovery=False, expected_revision=None):
        with parallel.pool_lock(), self.store.locked():
            path = self.store._path(key)
            r = self.store._read(path)
            if any(self.store._read(p).attempt.epoch > r.attempt.epoch
                   for p in self.store.root.glob('*.json')
                   if self.store._read(p).invocation.invocation_id == r.invocation.invocation_id):
                raise StateConflict('newer epoch exists')
            evidence = (r.receipt or {}).get('pre_dispatch_failure')
            if evidence:
                if evidence.get('reason') != reason or r.state != 'failed' or r.reservation:
                    raise StateConflict('failure evidence mismatch')
                reservation = Reservation.from_dict(evidence['reservation'])
            else:
                if expected_revision is not None and r.revision != expected_revision:
                    raise StateConflict('proof revision changed')
                untouched(r, recovery=recovery)
                reservation = Reservation.from_dict(r.reservation)
                if reservation.key != r.key or reservation.store_root != str(self.store.root):
                    raise StateConflict('reservation mismatch')
                evidence = {'reason': reason, 'proof': proof, 'reservation': asdict(reservation)}
            if reservation.key != r.key or reservation.store_root != str(self.store.root):
                raise StateConflict('reservation identity mismatch')
            reservation_path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
            if reservation_path.exists():
                if json.loads(reservation_path.read_text()) != json.loads(json.dumps(asdict(reservation))):
                    raise StateConflict('pool reservation mismatch')
            elif not (r.receipt or {}).get('pre_dispatch_failure'):
                raise StateConflict('pool reservation missing')
            if not (r.receipt or {}).get('pre_dispatch_failure'):
                r.receipt = dict(r.receipt or {}, pre_dispatch_failure=evidence)
                r.outcome = {'status': 'failed', 'backend_exit_code': 1, 'quiescent': True,
                             'provenance': ('creation_lifecycle' if reason == 'failed_child_creation'
                                            else 'pre_dispatch_schema'), 'reason': reason}
                r.quiescence = {'confirmed': True, 'evidence': (reason if reason == 'failed_child_creation'
                                else 'schema rejected before network dispatch'),
                                'observed_at': time.time()}
                r.state = 'failed'; r.finished_at = time.time(); r.reservation = None
                r.revision += 1
                atomic_json(path, r.to_dict())
            # Crash after CAS is repaired by the immutable exact reservation receipt.
            reservation_path.unlink(missing_ok=True)
            fd = os.open(reservation_path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return r


def recover(store, key, source, package_root, *, apply=False, validator=None, target=None):
    from .paseo_controller import lifecycle_lock, records_for
    with lifecycle_lock(store):
        r = store.get(key)
        if Path(r.invocation.source_cwd).resolve() != Path(source).resolve():
            raise StateConflict('wrong repo')
        if records_for(store, r.invocation.invocation_id)[-1].key != r.key:
            raise StateConflict('latest exact epoch required')
        admission = PreDispatchAdmission(store, None, None)
        prior = (r.receipt or {}).get('pre_dispatch_failure')
        if prior and prior.get('reason') in ('invalid_bound_workspace_id', 'failed_child_creation'):
            return admission.fail(key, prior['proof'], prior['reason']) if apply else r
        transport = untouched(r, recovery=True)
        if transport.get('pending') == 'create':
            request = dict(transport, command='creation-failure', target=target)
            proof = creation_proof(request, package_root, validator)
            expected = {'ok': True, 'targetKey': r.attempt.target_key,
                        'agentId': r.attempt.agent_id, 'agentKey': transport['agentKey'],
                        'workspaceId': r.attempt.workspace_id, 'phase': 'failed',
                        'outcomeUnknown': False, 'inFlight': None,
                        'absence': 'AGENT_NOT_FOUND'}
            if proof != expected:
                raise StateConflict('failed exact creation not proved')
            return admission.fail(key, proof, 'failed_child_creation', recovery=True,
                                  expected_revision=r.revision) if apply else r
        if not isinstance(r.attempt.workspace_id, str):
            raise StateConflict('bound workspace required')
        request = {'command': 'validate-workspace-id', 'workspaceId': r.attempt.workspace_id}
        if validator is None:
            try:
                process = subprocess.run(['node', str(Path(__file__).with_name('paseo_bridge.mjs')),
                                          str(package_root)], input=json.dumps(request),
                                         capture_output=True, text=True, timeout=10, check=False)
                proof = json.loads(process.stdout)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                raise StateConflict('schema proof unavailable') from None
        else:
            proof = validator(request)
        if not trusted_schema_rejection(proof, 'workspace') or any(
                issue['path'] != ['workspaceId'] for issue in proof['issues']):
            raise StateConflict('invalid bound workspace not proved')
        return admission.fail(key, proof, 'invalid_bound_workspace_id', recovery=True,
                              expected_revision=r.revision) if apply else r


def creation_proof(request, package_root, validator):
    """Read-only public lifecycle observation; never fall back after API failure."""
    if validator is not None:
        return validator(request)
    try:
        process = subprocess.run(['node', str(Path(__file__).with_name('paseo_bridge.mjs')),
                                  str(package_root)], input=json.dumps(request),
                                 capture_output=True, text=True, timeout=10, check=False)
        return json.loads(process.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise StateConflict('creation proof unavailable') from None
