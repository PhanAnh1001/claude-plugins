"""Pinned official Paseo transport. No shell writer fallback or implicit retry.

The optional store is the shared ExecutionStore get/CAS API. Transport metadata
lives in record.receipt['transport']; placement is bound into the immutable Attempt.
Admission, quiescence and review come from persisted controller/supervisor evidence.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import time
from pathlib import Path
import subprocess
import uuid


class TransportError(RuntimeError):
    """Safe machine code, never upstream diagnostics."""


class PaseoTransport:
    def __init__(self, package_root, target, client_factory=None, *, store=None, node='node'):
        self.package_root = Path(package_root)
        try:
            package = json.loads((self.package_root / 'package.json').read_text())
            if not self.package_root.is_absolute() or package.get('name') != '@getpaseo/cli' or package.get('version') != '0.15.0' or package.get('type') != 'module':
                raise ValueError()
        except Exception:
            raise TransportError('PACKAGE_UNSUPPORTED') from None
        self.target = dict(target)
        kind = target.get('kind')
        if kind not in ('instance', 'endpoint'):
            raise TransportError('TARGET_INVALID')
        identity = [kind, target.get('home' if kind == 'instance' else 'host')]
        if not isinstance(identity[1], str) or not identity[1]:
            raise TransportError('TARGET_INVALID')
        self.target_key = hashlib.sha256(json.dumps(identity, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        self.store, self.client_factory, self.node = store, client_factory, node

    def _call(self, command, data=None, *, timeout_s=10):
        request = dict(data or {}, command=command, targetKey=self.target_key, target=self.target)
        try:
            if self.client_factory:
                result = self.client_factory(self.package_root, self.target)(request)
            else:
                process = subprocess.run([self.node, str(Path(__file__).with_name('paseo_bridge.mjs')), str(self.package_root)],
                    input=json.dumps(request), text=True, capture_output=True, timeout=timeout_s, check=False)
                result = json.loads(process.stdout)
            if not isinstance(result, dict):
                raise ValueError()
        except Exception:
            return {'ok': False, 'code': 'TRANSPORT_UNRESOLVED'}
        if result.get('ok') and result.get('targetKey') != self.target_key:
            raise TransportError('TARGET_MISMATCH')
        return result

    def probe_capabilities(self):
        return self._call('probe')

    def verify_parent(self, parent_agent_id):
        result = self._call('parent', {'parentAgentId': parent_agent_id})
        if not result.get('ok'):
            raise TransportError('PARENT_UNVERIFIED')
        return result

    def _read(self, key):
        if self.store is None:
            raise TransportError('DURABLE_STORE_REQUIRED')
        source = self.store.get(key)
        record = deepcopy((source.receipt or {}).get('transport', {}))
        record['_source_transport'] = deepcopy((source.receipt or {}).get('transport', {}))
        record['revision'] = source.revision
        record['requestKey'] = source.attempt.request_key
        fields = {'targetKey':'target_key','projectId':'project_id',
                  'workspaceId':'workspace_id','agentId':'agent_id'}
        for public, field in fields.items():
            value = getattr(source.attempt, field)
            if value is not None:
                if public in record and record[public] != value:
                    raise TransportError('PLACEMENT_MISMATCH')
                record[public] = value
        record['parentAgentId'] = source.invocation.parent_paseo_agent_id
        record['cwd'] = source.invocation.isolated_cwd
        record['admitted'] = bool(source.reservation)
        backend = source.invocation.backend
        if backend in ('claude', 'claude-main'):
            backend = 'claude-v2' if backend == 'claude' else 'claude-v1'
        record['expectedProviderId'] = 'hh-hand-' + backend
        record['model'] = source.invocation.model
        record['effort'] = source.invocation.effort
        record['gatewayEnv'] = {'HYBRID_HANDS_EXECUTION_ROOT': str(self.store.root),
            'HYBRID_HANDS_INVOCATION_ID': source.invocation.invocation_id}
        q = source.quiescence or {}
        record['quiescent'] = (q.get('confirmed') is True and bool(q.get('evidence')))
        record['freshDispatch'] = (bool(source.reservation) and source.writer is None
            and source.process is None and source.outcome is None
            and not record.get('sendConfirmed') and source.state == 'admitted')
        record['reviewed'] = (source.artifacts.get('review') or {}).get('approved') is True
        if record.get('targetKey', self.target_key) != self.target_key:
            raise TransportError('TARGET_MISMATCH')
        return record

    def _save(self, key, record, **changes):
        # Gateway/worker may publish receipts during sendMessage. Merge only
        # their independent fields; a competing transport operation still fences us.
        from .execution_state import StateConflict
        for _ in range(8):
            source = self.store.get(key)
            if (source.receipt or {}).get('transport', {}) != record['_source_transport']:
                raise TransportError('STATE_CONFLICT')
            updated = dict(record, **changes)
            updated.pop('_source_transport', None)
            fields = {'targetKey':'target_key','projectId':'project_id',
                      'workspaceId':'workspace_id','agentId':'agent_id'}
            bindings = {}
            for public, field in fields.items():
                if public in updated:
                    before = getattr(source.attempt, field)
                    if before is not None and before != updated[public]:
                        raise TransportError('PLACEMENT_MISMATCH')
                    bindings[field] = updated[public]
            source.attempt = replace(source.attempt, **bindings)
            source.receipt = dict(source.receipt or {}, transport=updated)
            try:
                self.store.compare_and_swap(key, source.revision, source)
                return self._read(key)
            except StateConflict:
                continue
        raise TransportError('STATE_CONFLICT')

    def _mutate(self, key, command, **extra):
        record = self._read(key)
        if command == 'cancel':
            if record.get('cancelPending'):
                return {'ok':False, 'state':'unresolved', 'code':'CANCEL_RECONCILE_REQUIRED'}
            if not Path(record['cwd']).is_dir():
                raise TransportError('CWD_MISSING')
            record = self._save(key, record, cancelPending=True)
            result = self._call(command, {k: v for k, v in record.items() if k != '_source_transport'})
            if result.get('ok'):
                self._save(key, record, cancelPending=False, cancelConfirmed=True)
                result['state'] = 'cancel_requested'  # Not process quiescence.
            return result
        if record.get('pending'):
            return {'ok': False, 'state': 'unresolved', 'code': 'RECONCILE_REQUIRED'}
        if not Path(record['cwd']).is_dir():
            raise TransportError('CWD_MISSING')
        # Durable intent also fences a concurrent caller. Never resend pending op.
        if command in ('workspace','create') and not record.get('admitted'):
            raise TransportError('ADMISSION_REQUIRED')
        if command == 'send':
            if not (record.get('admitted') and (record.get('quiescent') or record.get('freshDispatch'))):
                raise TransportError('ADMISSION_REQUIRED')
        record = self._save(key, record, pending=command)
        if command == 'send' and record.get('freshDispatch'):
            record['quiescent'] = True
        result = self._call(command, dict({k: v for k, v in record.items() if k != '_source_transport'}, **extra))
        if result.get('ok'):
            record = self._save(key, record, pending=None, **{command + 'Confirmed': True})
        return dict(result, placement={k: record.get(k) for k in
            ('targetKey', 'projectId', 'workspaceId', 'agentId', 'parentAgentId', 'cwd', 'providerId')})

    def ensure_workspace(self, key, verified_project, isolated_cwd):
        cwd = str(Path(isolated_cwd).resolve())
        if not Path(cwd).is_dir():
            raise TransportError('CWD_MISSING')
        verified = self.verify_parent(verified_project['parentAgentId'])
        if verified.get('projectId') != verified_project.get('projectId'):
            raise TransportError('PROJECT_MISMATCH')
        record = self._read(key)
        proposed = dict(targetKey=self.target_key, projectId=verified['projectId'],
            parentAgentId=verified['parentAgentId'], cwd=cwd)
        if any(k in record and record[k] != v for k, v in proposed.items()):
            raise TransportError('PLACEMENT_MISMATCH')
        if record.get('workspaceConfirmed'):
            return record
        capability = self.probe_capabilities()
        if not capability.get('ok') or record['expectedProviderId'] not in capability.get('providers', []):
            raise TransportError('PROVIDER_UNAVAILABLE')
        if record.get('workspaceId') and not record.get('workspaceKey'):
            result = self._call('verify-workspace', record)
            if not result.get('ok'):
                return result
            return self._save(key, record, workspaceConfirmed=True)
        if not record.get('workspaceId'):
            record = self._save(key, record, **proposed, workspaceId=str(uuid.uuid4()),
                agentId=str(uuid.uuid4()), workspaceKey=str(uuid.uuid4()))
        return self._mutate(key, 'workspace')

    def create_child(self, key, placement, *, caller_agent_id, provider_id):
        record = self._read(key)
        if provider_id != record['expectedProviderId']:
            raise TransportError('PROVIDER_MISMATCH')
        if caller_agent_id != record['parentAgentId']:
            raise TransportError('PARENT_MISMATCH')
        placement = placement.get('placement', placement)
        if any(placement.get(k) != record.get(k) for k in ('projectId','workspaceId','cwd')):
            raise TransportError('PLACEMENT_MISMATCH')
        if record.get('providerId', provider_id) != provider_id:
            raise TransportError('PROVIDER_MISMATCH')
        if record.get('createConfirmed'):
            return record
        if not record.get('workspaceConfirmed'):
            raise TransportError('WORKSPACE_UNCONFIRMED')
        if not record.get('workspaceKey') and not record.get('agentKey'):
            record = self._save(key, record, providerId=provider_id)
            result = self._call('verify-child', record)
            if not result.get('ok'):
                return result
            return self._save(key, record, createConfirmed=True)
        if not record.get('agentKey'):
            self._save(key, record, providerId=provider_id, agentKey=str(uuid.uuid4()))
        return self._mutate(key, 'create')

    def send_prompt(self, key, brief):
        record = self._read(key)
        if record.get('briefDigest') and record['briefDigest'] != hashlib.sha256(brief.encode()).hexdigest():
            raise TransportError('PROMPT_MISMATCH')
        if record.get('sendConfirmed'):
            return {'ok':True, 'state':'delivered', 'messageId':record['messageId']}
        if not record.get('admitted') or not (record.get('quiescent') or record.get('freshDispatch')):
            raise TransportError('ADMISSION_REQUIRED')
        if not record.get('createConfirmed'):
            raise TransportError('CHILD_UNCONFIRMED')
        if not record.get('messageId'):
            record = self._save(key, record, messageId=record['requestKey'],
                briefDigest=hashlib.sha256(brief.encode()).hexdigest())
        elif record.get('briefDigest') != hashlib.sha256(brief.encode()).hexdigest():
            raise TransportError('PROMPT_MISMATCH')
        return self._mutate(key, 'send', brief=brief)

    def reconcile(self, key):
        record = self._read(key)
        result = self._call('reconcile', record)
        expected = {'workspace':'workspace_verified', 'create':'child_verified', 'send':'delivered', 'archive':'archived', 'reopen':'reopened'}
        pending = record.get('pending')
        if result.get('ok') and pending in expected and result.get('state') == expected[pending]:
            self._save(key, record, pending=None, **{pending+'Confirmed':True})
        return result

    def wait_child(self, key, timeout_s, poll_interval=0.1, *, require_settlement=False):
        """Bounded read-only wait; public idle/receipt never proves completion.

        Completion means a terminal outcome AND supervisor evidence for this exact
        epoch, not a successful backend exit. The authoritative outcome is returned
        unchanged. No refresh, daemon mutation, resend or shell fallback occurs.
        """
        if (not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s)
                or timeout_s < 0 or not isinstance(poll_interval, (int, float))
                or not math.isfinite(poll_interval) or poll_interval <= 0):
            raise TransportError('WAIT_INVALID')
        deadline = time.monotonic() + timeout_s
        observation = None
        while True:
            record = self._read(key)
            source = self.store.get(key)
            q = source.quiescence or {}
            if (source.outcome is not None and source.outcome.get('quiescent') is True
                    and q.get('confirmed') is True and q.get('evidence')
                    and (not require_settlement or (not source.reservation and source.state in ('awaiting_review', 'archived')))):
                return {'ok': True, 'state': 'completed', 'outcome': deepcopy(source.outcome)}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {'ok': True, 'state': 'unresolved', 'observation': observation}
            # Do not use reconcile() here: waiting does not settle transport intents.
            # Injected clients must honor their own bounded request contract.
            observation = self._call('reconcile', record, timeout_s=min(10, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {'ok': True, 'state': 'unresolved', 'observation': observation}
            time.sleep(min(poll_interval, remaining, 1.0))

    def cancel_child(self, key):
        return self._mutate(key, 'cancel')

    def archive_child(self, key):
        record = self._read(key)
        if not record.get('reviewed') or not record.get('quiescent'):
            raise TransportError('REVIEW_REQUIRED')
        return self._mutate(key, 'archive')

    def reopen_child(self, key):
        if not self._read(key).get('quiescent'):
            raise TransportError('QUIESCENCE_REQUIRED')
        return self._mutate(key, 'reopen')
