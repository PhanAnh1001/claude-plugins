"""Durable completion sinks for managed workers; recovery never repeats apply.

Bind before dispatch; attach in the daemon using only its execution store. No
frontend objects, environment snapshots, credentials or prompt are serialized.
"""
from dataclasses import asdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile

from . import isolation, go_usage, codex_usage, quota_state
from .backends.base import Quota
from .execution_state import StateConflict, _plain, atomic_json
from .execution_admission import Reservation
from .legacy_attestation import settlement_authorized
from .locked_json import locked, read_json, write_atomic


def serialize_context(ctx):
    return _plain({k: str(v) if isinstance(v, Path) else v for k, v in asdict(ctx).items()})


def reconstruct_context(data):
    data = dict(data)
    for name in ('source_root', 'run_cwd', 'worktree', 'worktree_root'):
        if data.get(name) is not None:
            data[name] = Path(data[name])
    return isolation.IsolationContext(**data)


def _text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class CompletionService:
    def __init__(self, store, supervisor, admission):
        self.store, self.supervisor, self.admission = store, supervisor, admission
        self.worker = None

    def bind(self, key, ctx, *, ledger_path, registry_dir, policy='no_apply',
             go_ledger=None, go_summary=None, go_monthly_limit=0,
             codex_ledger=None, quota_path=None, label=''):
        """Persist prepared context and sink paths. MVP always retains worktree.

        policy: no_apply/check snapshot without source mutation; apply permits
        source apply only on successful authoritative terminal outcome.
        """
        if policy not in ('no_apply', 'check', 'apply'):
            raise ValueError('invalid completion policy')
        r = self.store.get(key)
        if ctx.mode != 'worktree' or ctx.worktree is None:
            raise ValueError('managed completion requires prepared worktree')
        if Path(ctx.run_cwd).resolve() != Path(r.invocation.isolated_cwd).resolve() or not Path(r.invocation.source_cwd).resolve().is_relative_to(Path(ctx.source_root).resolve()):
            raise ValueError('prepared context identity mismatch')
        config = dict(version=1, context=serialize_context(ctx), policy=policy, label=str(label),
                      ledger=str(Path(ledger_path).resolve()), registry=str(Path(registry_dir).resolve()),
                      go_ledger=str(Path(go_ledger).resolve()) if go_ledger else None,
                      go_summary=str(Path(go_summary).resolve()) if go_summary else None,
                      go_monthly_limit=go_monthly_limit,
                      codex_ledger=str(Path(codex_ledger).resolve()) if codex_ledger else None,
                      quota_path=str(Path(quota_path).resolve()) if quota_path else None)
        if r.receipt and r.receipt.get('completion'):
            if r.receipt['completion'] != config: raise StateConflict('completion binding immutable')
            return
        if r.writer or r.settle_keys: raise StateConflict('bind completion before launch')
        r.receipt = dict(r.receipt or {}, completion=config)
        self.store.compare_and_swap(key, r.revision, r)

    def attach(self, worker):
        self.worker = worker
        worker.hooks = {kind: self._hook(kind) for kind in ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state')}
        worker.settlement_callback = self.release
        return self

    def _config(self, record):
        config = (record.receipt or {}).get('completion')
        if not config or config.get('version') != 1: raise StateConflict('completion binding required')
        return config

    def _proof(self, r, kind):
        return Path(r.receipt['worker_run_dir']) / ('.completion-' + kind + '.json')

    def _hook(self, kind):
        def run(key, token, r, outcome):
            config = self._config(r)
            if r.outcome and r.outcome.get('reason') == 'usage observation unresolved':
                raise StateConflict('usage observation unresolved')
            if not outcome or not outcome.quiescent or not settlement_authorized(self.supervisor, key):
                raise StateConflict('authoritative quiescence required')
            run_dir = Path(r.receipt['worker_run_dir'])
            run_dir.mkdir(parents=True, exist_ok=True)
            refs = getattr(self, '_' + kind)(r, config, token, run_dir)
            atomic_json(self._proof(r, kind), dict(key=token, refs=refs))
            return refs
        return run

    def _finalize(self, r, c, token, run_dir):
        ctx = reconstruct_context(c['context'])
        apply = c['policy'] == 'apply' and r.outcome['status'] == 'ok' and r.outcome.get('backend_exit_code') in (0, None)
        result = isolation.finalize(ctx, run_dir, apply_changes=apply,
                                    skip_reason='managed policy: ' + c['policy'] if r.outcome['status'] == 'ok' else 'failed execution; preserve patch')
        if result.status == isolation.APPLY_ERROR: raise StateConflict('finalization failed; preserve worktree')
        data = serialize_result(result)
        if c['policy'] == 'check' and result.patch_path and result.patch_path.stat().st_size:
            checked = isolation._git(['apply', '--check', str(result.patch_path)], ctx.source_root, ok=False)
            data['check_ok'] = checked.returncode == 0
        return dict(result=data, kept=True, patch_sha256=hashlib.sha256(result.patch_path.read_bytes()).hexdigest() if result.patch_path else None)

    def _entry(self, r, token):
        iso = lambda t: dt.datetime.fromtimestamp(t).astimezone().isoformat() if t is not None else None
        i = r.invocation
        run_id = r.attempt.run_id or hashlib.sha256(json.dumps(_plain(r.key), sort_keys=True).encode()).hexdigest()
        if not run_id or run_id in ('.', '..') or Path(run_id).name != run_id or '\\' in run_id:
            raise StateConflict('invalid run id')
        return dict(run_id=run_id,
                    execution_key=_plain(r.key), idempotency_key=token, backend=i.backend, model=i.model,
                    effort=i.effort, label=self._config(r).get('label', ''), cwd=i.source_cwd, parent_session=i.parent_session,
                    started=iso(r.started_at), started_at=r.started_at, ended=iso(r.finished_at), ended_at=r.finished_at,
                    status=r.outcome['status'], exit_code=r.outcome.get('backend_exit_code'),
                    duration_seconds=max(0, r.finished_at - r.started_at) if r.finished_at is not None and r.started_at is not None else None,
                    tokens=r.outcome.get('usage'), quota=(r.receipt.get('usage_observation', {}).get('quota') or {'used_percent': None, 'resets_at': None}))

    def _report(self, r, c, token, run_dir):
        entry = self._entry(r, token)
        ctx = reconstruct_context(c['context'])
        result = dict(r.artifacts['finalize']['result'])
        result.pop('check_ok', None)
        if result.get('patch_path'): result['patch_path'] = Path(result['patch_path'])
        block = isolation.report_block(ctx, isolation.ApplyResult(**result), kept=True)
        _text(run_dir / 'report.md', (r.outcome.get('final_text') or '').rstrip() + '\n\n' + block + '\n')
        metadata = dict(entry, base_commit=ctx.base_commit, dirty=ctx.dirty, dirty_files=ctx.dirty_files,
                        invocation_id=r.key.invocation_id, attempt_id=r.key.attempt_id, epoch=r.key.epoch,
                        agent_id=r.attempt.agent_id, run_dir=str(run_dir),
                        report_sha256=hashlib.sha256((run_dir / 'report.md').read_bytes()).hexdigest())
        registry = Path(c['registry']) / (entry['run_id'] + '.json')
        registry.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(run_dir / 'meta.json', metadata)
        atomic_json(registry, metadata)
        return dict(report=str(run_dir / 'report.md'), metadata=str(run_dir / 'meta.json'), registry=str(registry))

    def _ledger(self, r, c, token, run_dir):
        path = Path(c['ledger']); path.parent.mkdir(parents=True, exist_ok=True)
        entry = self._entry(r, token)
        with locked(path):
            entries = read_json(path, [])
            matches = [x for x in entries if x.get('execution_key') == _plain(r.key)]
            if matches and matches != [entry]: raise StateConflict('ledger identity mismatch')
            if not matches: write_atomic(path, entries + [entry])
        return dict(path=str(path), key=token)

    def _go_ledger(self, r, c, token, run_dir):
        if r.invocation.backend != 'dsh': return dict(not_applicable=True)
        if not c['go_ledger'] or not c['go_summary']: raise StateConflict('Go sink binding required')
        entry = self._entry(r, token)
        cost, source = go_usage.resolve_cost(entry['tokens'] or {}, r.receipt.get('usage_observation', {}).get('go_allowance_usd'), go_usage.price_for({}, entry['model']))
        if entry['tokens'] is None: cost, source = None, go_usage.COST_UNKNOWN
        item = go_usage.build_record(entry['run_id'], entry['ended'], entry['backend'], entry['model'], entry['tokens'] or {}, cost, source, entry['cwd'])
        item.update(execution_key=_plain(r.key), idempotency_key=token)
        path = Path(c['go_ledger']); path.parent.mkdir(parents=True, exist_ok=True)
        with locked(path):
            records = go_usage._read_records_unlocked(path)
            matches = [x for x in records if x.get('execution_key') == _plain(r.key)]
            if matches and matches != [item]: raise StateConflict('Go sink mismatch')
            if not matches:
                records.append(item)
                _text(path, ''.join(json.dumps(x) + '\n' for x in records))
            go_usage.write_summary(Path(c['go_summary']), go_usage.summarize(records, c['go_monthly_limit'], r.finished_at))
        return dict(path=str(path), summary=c['go_summary'], key=token)

    def _usage_state(self, r, c, token, run_dir):
        observation = r.receipt.get('usage_observation', {})
        refs = {}
        if c['quota_path']:
            path = Path(c['quota_path']); path.parent.mkdir(parents=True, exist_ok=True)
            # Direct atomic projection keyed by execution, with a fixed completion
            # timestamp/backoff, so a crash cannot shift the exhaustion deadline.
            quota = observation.get('quota') or {}
            with locked(path):
                state = read_json(path, {})
                value = dict(state.get(r.invocation.backend, {}))
                value.update(updated=dt.datetime.fromtimestamp(r.finished_at, dt.timezone.utc).isoformat(),
                             execution_key=_plain(r.key))
                if quota.get('used_percent') is not None: value['used_percent'] = quota['used_percent']
                if quota.get('exhausted') or r.outcome['status'] == 'quota_exhausted':
                    reset = quota_state.parse_iso(quota.get('resets_at'))
                    finished = dt.datetime.fromtimestamp(r.finished_at, dt.timezone.utc)
                    if reset is None or reset <= finished:
                        reset = finished + dt.timedelta(hours=quota_state.DEFAULT_QUOTA_BACKOFF_HOURS)
                    value['exhausted_until'] = quota_state.iso(reset)
                state[r.invocation.backend] = value
                write_atomic(path, state)
            refs['quota'] = str(path)
        if r.invocation.backend == 'codex' and c['codex_ledger']:
            entry = self._entry(r, token)
            cost = codex_usage.estimate_cost(entry['tokens'] or {}, codex_usage.price_for({}, entry['model'])) if entry['tokens'] is not None else None
            item = codex_usage.build_record(entry['run_id'], entry['ended'], entry['model'], entry['effort'], entry['tokens'] or {}, cost,
                                            'estimated' if cost is not None else 'unknown', str(codex_home(r)), observation.get('windows'))
            item.update(execution_key=_plain(r.key), idempotency_key=token)
            path = Path(c['codex_ledger']); path.parent.mkdir(parents=True, exist_ok=True)
            with locked(path):
                records = go_usage._read_records_unlocked(path)
                matches = [x for x in records if x.get('execution_key') == _plain(r.key)]
                if matches and matches != [item]: raise StateConflict('Codex sink mismatch')
                if not matches: _text(path, ''.join(json.dumps(x) + '\n' for x in records + [item]))
            refs['codex'] = str(path)
        return refs

    def reconcile(self, key):
        """Read-only sink recovery. An unproved in_progress sink holds the slot."""
        for kind in ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state'):
            r = self.store.get(key)
            marker = r.settle_keys.get(kind)
            if not marker or marker['state'] == 'completed': continue
            refs = self._recover_refs(r, kind, marker['key'])
            if refs is None: return False
            r.artifacts[kind] = refs
            r.settle_keys[kind] = dict(key=marker['key'], state='completed')
            self.store.compare_and_swap(key, r.revision, r)
        if self.worker: self.worker.reconcile(key)
        return self.release(key)

    def _recover_refs(self, r, kind, token):
        c = self._config(r)
        try:
            proof = json.loads(self._proof(r, kind).read_text())
        except (OSError, ValueError):
            proof = None
        refs = proof.get('refs') if proof and proof.get('key') == token else None
        try:
            if kind == 'ledger':
                entries = read_json(Path(c['ledger']), [])
                if [x for x in entries if x.get('execution_key') == _plain(r.key)] != [self._entry(r, token)]: return None
                return dict(path=c['ledger'], key=token)
            if kind == 'go_ledger' and r.invocation.backend == 'dsh':
                records = go_usage._read_records_unlocked(Path(c['go_ledger']))
                matches = [x for x in records if x.get('execution_key') == _plain(r.key)]
                if len(matches) != 1 or matches[0].get('idempotency_key') != token: return None
                summary = json.loads(Path(c['go_summary']).read_text())
                timestamp = summary.get('updated_at')
                if type(timestamp) not in (int, float): return None
                if summary != go_usage.summarize(records, c['go_monthly_limit'], timestamp): return None
                return dict(path=c['go_ledger'], summary=c['go_summary'], key=token)
            if kind == 'report':
                run_dir = Path(r.receipt['worker_run_dir'])
                metadata = json.loads((run_dir / 'meta.json').read_text())
                registry = Path(c['registry']) / (self._entry(r, token)['run_id'] + '.json')
                if metadata.get('idempotency_key') != token or metadata.get('execution_key') != _plain(r.key): return None
                if json.loads(registry.read_text()) != metadata: return None
                if hashlib.sha256((run_dir / 'report.md').read_bytes()).hexdigest() != metadata.get('report_sha256'): return None
                return dict(report=str(run_dir / 'report.md'), metadata=str(run_dir / 'meta.json'), registry=str(registry))
            if refs is None: return None
            for name in ('path', 'summary', 'report', 'metadata', 'registry', 'quota', 'codex'):
                if name in refs and not Path(refs[name]).is_file(): return None
            if kind == 'finalize':
                patch = refs['result'].get('patch_path')
                if patch and hashlib.sha256(Path(patch).read_bytes()).hexdigest() != refs.get('patch_sha256'): return None
            return refs
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def release(self, key):
        r = self.store.get(key)
        if r.state == 'awaiting_review' and not r.reservation: return True
        if not r.outcome or not r.outcome.get('quiescent'): return False
        if any(r.settle_keys.get(k, {}).get('state') != 'completed' for k in ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state')): return False
        if not r.reservation: return False
        for kind, marker in r.settle_keys.items():
            if kind in ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state') and self._recover_refs(r, kind, marker['key']) is None: return False
        self.admission.release(Reservation.from_dict(r.reservation), outcome=r.outcome, artifacts_settled=True)
        return True


def serialize_result(result):
    return {k: str(v) if isinstance(v, Path) else v for k, v in asdict(result).items()}


def codex_home(record):
    from .backends.codex import home_dir
    return home_dir(_plain(record.invocation.fixed_options).get('options', {}))
