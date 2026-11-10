"""Trusted G3 dispatcher. Transport uncertainty never authorizes a second writer."""
from __future__ import annotations

import argparse
import hashlib
import fcntl
from contextlib import contextmanager
import json
import math
from dataclasses import replace
from pathlib import Path
import os
import re
import sys
import time
import uuid

from . import isolation, parallel
from .config import load_config
from .constants import EXIT_ALL_UNAVAILABLE, EXIT_FAIL, EXIT_PARALLEL_FULL, EXIT_USAGE, HAND_RUNS_SUBDIR
from .execution_admission import (AdmissionController, AdmissionDenied, AdmissionFull,
                                  AdmissionConflict)
from .execution_state import Invocation, Attempt, ExecutionStore, StateConflict, _plain
from .execution_supervisor import ExecutionSupervisor
from .paseo_transport import PaseoTransport, TransportError

MODES = ('shell', 'auto', 'paseo-required')
ALIASES = {'claude-main': 'claude-v1', 'claude': 'claude-v2'}
LIFECYCLE_LOCK_TIMEOUT = 10
LIFECYCLE_LOCK_POLL = 0.05


@contextmanager
def lifecycle_lock(store, name='.gateway-lock'):
    with (store.root / name).open('a') as lock:
        deadline = time.monotonic() + LIFECYCLE_LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StateConflict('lifecycle busy') from None
                time.sleep(LIFECYCLE_LOCK_POLL)
        yield


def canonical_backend(name):
    return ALIASES.get(name, name)


def account_for(name):
    return 'gpt' if name == 'codex' else canonical_backend(name)


class PaseoUnavailable(RuntimeError):
    """Only daemon/provider/capability absence before any mutation allows fallback."""


class ExecutionUnresolved(RuntimeError):
    pass


class FreshPolicy:
    """Read effective repo policy anew, including account/day/quota guards per prompt."""
    def __init__(self, store):
        self.store = store

    def max_parallel(self, invocation):
        return load_config(Path(invocation.source_cwd)).max_parallel

    def __call__(self, invocation, attempt):
        from .run_cmd import auto_preflight, with_sandbox
        try:
            record = self.store.get(attempt.key)
            binding = (record.receipt or {}).get('controller')
            if not isinstance(binding, dict) or binding.get('version') != 1:
                return False
            if not valid_completion_binding(record):
                return False
            cfg = load_config(Path(invocation.source_cwd))
            if str(cfg.root.resolve()) != binding.get('policy_root'):
                return False
            if invocation.backend != canonical_backend(binding.get('backend')):
                return False
            if invocation.account_alias != account_for(invocation.backend):
                return False
            if invocation.backend not in [canonical_backend(n) for n in cfg.order]:
                return False
            options = with_sandbox(cfg, binding['backend'])
            expected = _plain(invocation.fixed_options)
            if (invocation.model != str(options.get('model', '')) or
                invocation.effort != str(options.get('effort', options.get('variant', ''))) or
                expected.get('options') != options or
                expected.get('sandbox') != cfg.sandbox):
                return False
            # Only the already selected backend is tested: no backend/account retarget.
            pinned = replace(cfg, order=[binding['backend']])
            ready = next(auto_preflight(pinned, browser=expected.get('browser', False)), None)
            if not ready or ready[0] is None:
                return False
            if attempt.epoch > 1:
                previous = [r for r in records_for(self.store, invocation.invocation_id)
                            if r.attempt.epoch < attempt.epoch]
                if not previous:
                    return False
                prior = previous[-1]
                reviewed = (prior.artifacts.get('review') or {}).get('approved') is True
                capacity_retry = binding.get('capacity_continuation', 0)
                from .constants import DSH_CAPACITY_MAX_CONTINUATIONS
                automatic_capacity = (invocation.backend == 'dsh' and
                    type(capacity_retry) is int and 1 <= capacity_retry <= DSH_CAPACITY_MAX_CONTINUATIONS and
                    capacity_retry == (prior.receipt.get('controller', {}).get('capacity_continuation', 0) + 1) and
                    prior.receipt.get('usage_observation', {}).get('capacity_failure') is True)
                if not terminal_evidence(prior) or not (reviewed or automatic_capacity):
                    return False
            return True
        except (OSError, ValueError, TypeError, KeyError, StateConflict):
            return False


def persist_prompt(record, prompt, brief=None):
    suffix = hashlib.sha256(json.dumps(_plain(record.key), sort_keys=True).encode()).hexdigest()
    run_dir = Path(record.invocation.fixed_options['run_dir']) / suffix
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / 'prompt.md'
    if path.exists() and path.read_bytes().decode('utf-8') != prompt:
        raise StateConflict('execution prompt immutable')
    if not path.exists():
        with path.open('x', encoding='utf-8', newline='') as stream:
            stream.write(prompt)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(run_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    path = run_dir / 'brief.md'
    if not path.exists():
        path.write_text(prompt if brief is None else brief, encoding='utf-8')


def pin_prompt(store, record, brief):
    from .paseo_prompt import prompt_path, trim
    path = prompt_path(record)
    if path.exists():
        pinned = path.read_bytes().decode('utf-8')
        if trim(pinned) != trim(brief):
            raise StateConflict('execution prompt immutable')
        brief = pinned
    else:
        brief = trim(brief)
        persist_prompt(record, brief)
    digest = hashlib.sha256(brief.encode()).hexdigest()
    record = store.get(record.key)
    if (record.receipt or {}).get('brief_digest', digest) != digest:
        raise StateConflict('pinned digest mismatch')
    if 'brief_digest' not in (record.receipt or {}):
        record.receipt = dict(record.receipt or {}, brief_digest=digest)
        store.compare_and_swap(record.key, record.revision, record)
    return brief


def emit_managed_result(record):
    report = record.artifacts.get('report', {}).get('report')
    print(f"hand-ext: {record.invocation.backend} {(record.outcome or {}).get('status', 'unknown')}")
    print(f"invocation: {record.key.invocation_id} attempt: {record.key.attempt_id} epoch: {record.key.epoch}")
    if report:
        print(f'report: {report}')


def valid_completion_binding(record):
    from .paseo_completion import reconstruct_context
    try:
        config = record.receipt['completion']
        if config['version'] != 1 or config['policy'] not in ('no_apply', 'check', 'apply'):
            return False
        ctx = reconstruct_context(config['context'])
        invocation = record.invocation
        if (ctx.mode != 'worktree' or ctx.worktree is None or
            ctx.source_root.resolve() != Path(invocation.source_cwd).resolve() or
            ctx.run_cwd.resolve() != Path(invocation.isolated_cwd).resolve() or
            not ctx.run_cwd.is_dir() or not ctx.worktree.is_dir() or
            not re.fullmatch(r'[a-f0-9]{40,64}', ctx.baseline_tree)):
            return False
        if any(not isinstance(config.get(k), str) or not Path(config[k]).is_absolute()
               for k in ('ledger', 'registry')):
            return False
        if invocation.backend == 'dsh' and any(not config.get(k) for k in ('go_ledger', 'go_summary')):
            return False
        return isolation._git(['cat-file', '-e', ctx.baseline_tree + '^{tree}'], ctx.worktree, ok=False).returncode == 0
    except (OSError, ValueError, TypeError, KeyError):
        return False


def terminal_evidence(record):
    """A released settled epoch retains its daemon authority after frontend restart."""
    from .legacy_attestation import attested
    q = record.quiescence or {}
    return (record.outcome is not None and record.outcome.get('quiescent') is True
            and (q.get('confirmed') is True or attested(record)) and bool(q.get('evidence'))
            and record.reservation is None
            and all(record.settle_keys.get(k, {}).get('state') == 'completed'
                    for k in ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state')))


def lifecycle_diagnostic(store, key, operation):
    """Safe durable retry receipt; never store provider exception text."""
    for _ in range(8):
        record = store.get(key)
        record.receipt = dict(record.receipt or {}, lifecycle_error=dict(
            operation=operation, code=operation.upper() + '_UNRESOLVED'))
        try:
            return store.compare_and_swap(key, record.revision, record)
        except StateConflict:
            continue
    raise StateConflict('lifecycle receipt busy')


def archive_settled(store, transport, key):
    """One bounded attempt, outcome and settlement artifacts remain authoritative."""
    with lifecycle_lock(store, '.send-lock'), lifecycle_lock(store):
        record = store.get(key)
        key = record.key
        if records_for(store, record.invocation.invocation_id)[-1].key != key:
            raise StateConflict('archive requires latest exact execution')
        if record.state not in ('awaiting_review', 'archived') or not terminal_evidence(record):
            raise StateConflict('exact child not ready for archive')
        try:
            result = transport.archive_child(key)
            if not result.get('ok') or result.get('state') != 'archived':
                raise TransportError('ARCHIVE_UNRESOLVED')
        except (TransportError, StateConflict):
            lifecycle_diagnostic(store, key, 'archive')
            return store.get(key)
        record = store.get(key)
        record.state = 'archived'
        record.receipt.pop('lifecycle_error', None)
        return store.compare_and_swap(key, record.revision, record)


def records_for(store, invocation_id):
    with store.locked():
        rows = [store._read(p) for p in store.root.glob('*.json')]
    return sorted((r for r in rows if r.invocation.invocation_id == invocation_id),
                  key=lambda r: r.attempt.epoch)


class PaseoController:
    def __init__(self, cfg, store, transport, *, supervisor=None, admission=None,
                 completion=None):
        self.cfg, self.store, self.transport = cfg, store, transport
        self.supervisor = supervisor or ExecutionSupervisor(store)
        self.admission = admission or AdmissionController(store, self.supervisor, FreshPolicy(store))
        self.completion = completion

    def preflight(self, backend, parent_agent):
        """Read-only stage. No failure after this stage becomes shell fallback."""
        probe = self.transport.probe_capabilities()
        if not probe.get('ok'):
            if probe.get('code') in ('CAPABILITY_MISSING', 'CAPABILITY_UNCONFIRMED',
                                     'TRANSPORT_UNRESOLVED', 'DAEMON_UNAVAILABLE', 'BRIDGE_UNAVAILABLE'):
                raise PaseoUnavailable('PASEO_CAPABILITY_UNAVAILABLE')
            raise TransportError('PASEO_PROBE_FAILED')
        if 'hh-hand-' + canonical_backend(backend) not in probe.get('providers', []):
            raise PaseoUnavailable('PASEO_PROVIDER_UNAVAILABLE')
        if not parent_agent:
            raise PaseoUnavailable('PARENT_REQUIRED')
        return self.transport.verify_parent(parent_agent)

    def dispatch(self, invocation, attempt, brief, verified_parent):
        if self.completion is None:
            raise AdmissionDenied('completion binding required')
        existing = self.store.get(attempt.key)
        if (existing.receipt or {}).get('pre_dispatch_failure'):
            from .paseo_recovery import PreDispatchAdmission
            evidence = existing.receipt['pre_dispatch_failure']
            return PreDispatchAdmission(self.store, None, None).fail(
                attempt.key, evidence['proof'], evidence['reason'])
        brief = pin_prompt(self.store, existing, brief)
        self.admission.admit(invocation, attempt, max_parallel=self.cfg.max_parallel)
        # First mutation marks a one-way boundary. Any exception retains durable intent.
        try:
            workspace = self.transport.ensure_workspace(attempt.key, verified_parent,
                                                        invocation.isolated_cwd)
            if self._schema_failed(attempt.key, workspace, 'workspace'):
                return self.store.get(attempt.key)
            if workspace.get('ok') is False:
                raise ExecutionUnresolved('WORKSPACE_UNRESOLVED')
            child = self.transport.create_child(attempt.key, workspace,
                caller_agent_id=invocation.parent_paseo_agent_id,
                provider_id='hh-hand-' + invocation.backend)
            if self._schema_failed(attempt.key, child, 'create'):
                return self.store.get(attempt.key)
            if child.get('ok') is False:
                raise ExecutionUnresolved('CREATE_UNRESOLVED')
            sent = self.transport.send_prompt(attempt.key, brief)
            if self._schema_failed(attempt.key, sent, 'send'):
                return self.store.get(attempt.key)
            if not sent.get('ok'):
                raise ExecutionUnresolved('SEND_UNRESOLVED')
        except (TransportError, StateConflict) as exc:
            raise ExecutionUnresolved('DISPATCH_UNRESOLVED') from exc
        wait = self.transport.wait_child(attempt.key,
                                        invocation.fixed_options['timeout_s'] + 30, require_settlement=True)
        if wait.get('state') != 'completed':
            raise ExecutionUnresolved('EXECUTION_UNRESOLVED')
        record = self.store.get(attempt.key)
        if (record.receipt or {}).get('pre_dispatch_failure') and record.state == 'failed' and not record.reservation:
            return record
        if record.reservation or record.state not in ('awaiting_review', 'archived'):
            raise ExecutionUnresolved('SETTLEMENT_UNRESOLVED')
        # This frontend is independent of the gateway being archived. A failed
        # archive must never replace the backend's authoritative terminal result.
        try:
            return archive_settled(self.store, self.transport, attempt.key)
        except (TransportError, StateConflict):
            lifecycle_diagnostic(self.store, attempt.key, 'archive')
            return self.store.get(attempt.key)

    def _schema_failed(self, key, result, command):
        from .paseo_transport import trusted_schema_rejection
        from .paseo_recovery import PreDispatchAdmission
        proof = {k: v for k, v in result.items() if k != 'placement'}
        if not trusted_schema_rejection(proof, command):
            return False
        r = self.store.get(key)
        if (r.receipt or {}).get('transport', {}).get('schemaRejection') != proof:
            raise StateConflict('schema evidence not persisted')
        PreDispatchAdmission(self.store, None, None).fail(key, proof, 'request_schema_rejected',
                                                        expected_revision=r.revision)
        return True

    def continue_capacity(self, key, brief):
        """Existing DSH capacity policy: keep the accumulated isolated patch."""
        with lifecycle_lock(self.store):
            from .constants import DSH_CAPACITY_MAX_CONTINUATIONS
            old = self.store.get(key)
            if records_for(self.store, old.invocation.invocation_id)[-1].key != key:
                raise StateConflict('capacity continuation requires latest exact execution')
            count = old.receipt.get('controller', {}).get('capacity_continuation', 0)
            if (old.invocation.backend != 'dsh' or not terminal_evidence(old) or
                old.receipt.get('usage_observation', {}).get('capacity_failure') is not True or
                count >= DSH_CAPACITY_MAX_CONTINUATIONS):
                raise StateConflict('capacity continuation not authorized')
            self._restore(old, capacity=True)
            attempt = replace(old.attempt, attempt_id=str(uuid.uuid4()), epoch=old.attempt.epoch + 1,
                              request_key=str(uuid.uuid4()), run_id=None, thread_id=None)
            record = self.store.create_intent(old.invocation, attempt)
            record.receipt = {'controller': dict(old.receipt['controller'], capacity_continuation=count + 1),
                              'completion': dict(old.receipt['completion'])}
            self.store.compare_and_swap(record.key, record.revision, record)
            brief = pin_prompt(self.store, self.store.get(attempt.key), brief)
            self.admission.admit(old.invocation, attempt, max_parallel=self.cfg.max_parallel)
        parent = self.transport.verify_parent(old.invocation.parent_paseo_agent_id)
        return self.dispatch(old.invocation, attempt, brief, parent)

    def approve_review(self, key):
        with lifecycle_lock(self.store):
            record = self.store.get(key)
            if records_for(self.store, record.invocation.invocation_id)[-1].key != key:
                raise StateConflict('review requires latest exact execution')
            if (record.reservation or record.state not in ('awaiting_review', 'archived') or
                not terminal_evidence(record)):
                raise StateConflict('settled quiescent exact execution required')
            record = self.store.get(key)
            record.artifacts['review'] = {'approved': True, 'epoch': key.epoch}
            return self.store.compare_and_swap(key, record.revision, record)

    def archive(self, key):
        record = archive_settled(self.store, self.transport, key)
        # Explicit archive needs this attempt confirmed; soft failure keeps the
        # old state but leaves a safe lifecycle_error receipt.
        if record.state != 'archived' or (record.receipt or {}).get('lifecycle_error'):
            raise ExecutionUnresolved('ARCHIVE_UNRESOLVED')
        return record

    def _restore(self, old, *, capacity=False):
        # Restore before creating an epoch: failure leaves the reviewed latest key
        # retryable and cannot reserve capacity or create another writer.
        try:
            result = self.transport.reopen_child(old.key, **({'capacity': True} if capacity else {}))
            if not result.get('ok') or result.get('state') != 'reopened':
                raise TransportError('REOPEN_UNRESOLVED')
        except (TransportError, StateConflict) as exc:
            lifecycle_diagnostic(self.store, old.key, 'reopen')
            raise ExecutionUnresolved('REOPEN_UNRESOLVED') from exc
        record = self.store.get(old.key)
        record.receipt.pop('lifecycle_error', None)
        self.store.compare_and_swap(record.key, record.revision, record)

    def followup(self, key, brief):
        with lifecycle_lock(self.store):
            old = self.store.get(key)
            rows = records_for(self.store, old.invocation.invocation_id)
            if rows[-1].key != key:
                raise StateConflict('followup requires latest exact execution')
            if (old.reservation or old.state not in ('archived', 'awaiting_review') or
                (old.artifacts.get('review') or {}).get('approved') is not True or
                (old.artifacts.get('review') or {}).get('epoch') != key.epoch or
                not terminal_evidence(old)):
                raise StateConflict('review and quiescence required')
            if not isinstance(brief, str) or not brief.strip():
                raise ValueError('fresh self-contained brief required')
            self._restore(old)
            attempt = replace(old.attempt, attempt_id=str(uuid.uuid4()), epoch=old.attempt.epoch + 1,
                              request_key=str(uuid.uuid4()), run_id=None, thread_id=None)
            record = self.store.create_intent(old.invocation, attempt)
            bind_followup(self.store, old, record)
            # Fresh policy/admission still precedes every new send.
            brief = pin_prompt(self.store, self.store.get(attempt.key), brief)
            self.admission.admit(old.invocation, attempt, max_parallel=self.cfg.max_parallel)
        parent = self.transport.verify_parent(old.invocation.parent_paseo_agent_id)
        return self.dispatch(old.invocation, self.store.get(attempt.key).attempt, brief, parent)


def bind_followup(store, previous, record):
    """Fresh baseline prevents applying any earlier epoch patch twice."""
    from .paseo_completion import reconstruct_context, serialize_context
    binding = (previous.receipt or {}).get('completion')
    if not binding:
        raise AdmissionDenied('completion binding required')
    ctx = reconstruct_context(binding['context'])
    run_dir = Path(record.invocation.fixed_options['run_dir']) / ('baseline-' + record.attempt.attempt_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx.baseline_tree = isolation._snapshot_tree(ctx.worktree, run_dir, 'baseline')
    record.receipt = {'controller': dict(previous.receipt['controller']),
                      'completion': dict(binding, context=serialize_context(ctx))}
    return store.compare_and_swap(record.key, record.revision, record)


def transport_from_config(cfg, store):
    settings = cfg.paseo
    if not settings.get('package_root') or not isinstance(settings.get('target'), dict):
        raise PaseoUnavailable('PASEO_NOT_CONFIGURED')
    try:
        return PaseoTransport(settings['package_root'], settings['target'], store=store)
    except TransportError as exc:
        # Missing/unsupported pinned public API is a capability failure before dispatch.
        if str(exc) == 'PACKAGE_UNSUPPORTED':
            raise PaseoUnavailable('PASEO_PACKAGE_UNAVAILABLE') from exc
        raise


def _completion_service(store, supervisor, admission):
    """Small adapter boundary; the completion module owns all finalization side effects."""
    from .paseo_completion import CompletionService
    return CompletionService(store, supervisor, admission)


def cmd_managed_run(cfg, args, *, mode):
    from .run_cmd import (_cmd_shell_run, _resolve_parent_session, _new_run_id,
                          auto_preflight, safe_label, with_sandbox)
    from .prompt import read_brief, build_prompt
    if mode not in MODES:
        raise ValueError('invalid execution mode')
    browser = bool(getattr(args, 'browser', False))
    from .run_cmd import validate_browser
    validate_browser(args.backend, browser)
    selected_cfg = cfg if args.backend == 'auto' else replace(cfg, order=[args.backend])
    selected = next((b for b, _, _ in auto_preflight(selected_cfg, browser=browser)
                     if b is not None), None)
    if selected is None:
        return EXIT_ALL_UNAVAILABLE
    state_root = cfg.paseo.get('state_root') or str(cfg.machine_state_dir / 'executions')
    store = ExecutionStore(state_root)
    try:
        transport = transport_from_config(cfg, store)
        controller = PaseoController(cfg, store, transport)
        parent = controller.preflight(selected.name, os.environ.get('PASEO_AGENT_ID'))
    except PaseoUnavailable as exc:
        if mode == 'auto':
            # Keep the same selected backend and existing shell reservation semantics.
            if args.backend == 'auto':
                anchored = replace(cfg, order=cfg.order[cfg.order.index(selected.name):])
                return _cmd_shell_run(anchored, replace_args(args, mode='shell'))
            return _cmd_shell_run(cfg, replace_args(args, mode='shell'))
        print(f'hand-ext: {exc}', file=sys.stderr)
        return EXIT_FAIL
    except TransportError as exc:
        print(f'hand-ext: {exc}', file=sys.stderr)
        return EXIT_FAIL
    pinned_options = with_sandbox(cfg, selected.name)
    if ((getattr(args, 'model', None) and args.model != pinned_options.get('model')) or
        (getattr(args, 'effort', None) and args.effort != pinned_options.get('effort', pinned_options.get('variant'))) or
        (getattr(args, 'sandbox', None) and args.sandbox != cfg.sandbox)):
        print('hand-ext: managed model/effort/sandbox must match pinned repo policy', file=sys.stderr)
        return EXIT_USAGE
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    try:
        choice = isolation.resolve_choice(cfg, cwd, getattr(args, 'isolation', None))
    except isolation.IsolationError:
        print('hand-ext: invalid managed isolation', file=sys.stderr)
        return EXIT_USAGE
    if choice.mode != 'worktree':
        print('hand-ext: managed execution requires isolation=worktree', file=sys.stderr)
        return EXIT_USAGE
    brief = getattr(args, '_managed_brief', None)
    if brief is None:
        brief = read_brief(args.brief)
    prompt = build_prompt(brief, browser=browser)
    run_id = _new_run_id(safe_label(args), selected.name)
    try:
        completion = _completion_service(store, controller.supervisor, controller.admission)
        controller.completion = completion
        ctx = isolation.prepare(cfg, cwd, run_id, cfg.runs_dir / run_id, choice)
        if store.root.is_relative_to(ctx.run_cwd.resolve()):
            raise ValueError('execution state must be outside isolated writer cwd')
        opts = with_sandbox(cfg, selected.name)
        invocation = Invocation(str(uuid.uuid4()), parallel.scope_digest(cfg.root),
            _resolve_parent_session(cfg) or os.environ.get('PASEO_AGENT_ID', ''),
            os.environ.get('PASEO_AGENT_ID'), canonical_backend(selected.name),
            account_for(selected.name), str(opts.get('model', '')),
            str(opts.get('effort', opts.get('variant', ''))),
            'native_intent' if mode == 'paseo-required' else 'managed',
            str(ctx.source_root), str(ctx.run_cwd),
            {'run_dir': str(cfg.runs_dir / run_id), 'sandbox': cfg.sandbox,
             'timeout_s': (args.timeout_min if args.timeout_min is not None else cfg.timeout_min) * 60,
             'max_tokens': args.max_tokens if args.max_tokens is not None else cfg.max_tokens,
             'browser': browser, 'options': opts}, ('repo:*',))
        attempt = Attempt(invocation.invocation_id, str(uuid.uuid4()), 1, str(uuid.uuid4()), run_id=run_id)
        record = store.create_intent(invocation, attempt)
        record.receipt = {'controller': {'version': 1, 'policy_root': str(cfg.root.resolve()),
                                        'backend': selected.name, 'label': safe_label(args)}}
        store.compare_and_swap(record.key, record.revision, record)
        from . import codex_usage
        completion.bind(attempt.key, ctx, label=safe_label(args), ledger_path=cfg.ledger,
                        registry_dir=cfg.machine_state_dir / HAND_RUNS_SUBDIR,
                        policy='no_apply' if getattr(args, 'no_apply', False) else 'apply',
                        go_ledger=cfg.go_usage_ledger, go_summary=cfg.go_usage_summary,
                        go_monthly_limit=cfg.go_monthly_limit_usd,
                        codex_ledger=codex_usage.ledger_path(cfg), quota_path=cfg.quota_state)
        from .execution_worker import ExecutionWorker
        ExecutionWorker(store, controller.supervisor)._spec(invocation, attempt, prompt)
        if not math.isfinite(invocation.fixed_options['timeout_s']):
            raise ValueError('finite timeout required')
        if not valid_completion_binding(store.get(attempt.key)):
            raise ValueError('invalid completion binding')
        from .paseo_prompt import trim
        prompt = trim(prompt)
        persist_prompt(store.get(attempt.key), prompt, brief)
        result = controller.dispatch(invocation, attempt, prompt, parent)
        emit_managed_result(result)
        if (result.receipt or {}).get('pre_dispatch_failure'):
            return EXIT_FAIL
        from . import capacity
        from .backends import dsh as dsh_backend
        from .constants import DSH_CAPACITY_MAX_CONTINUATIONS
        locked_capacity_branch = False
        if args.backend == 'auto' and invocation.backend == 'dsh' and result.receipt.get('usage_observation', {}).get('capacity_failure') is True:
            threshold = dsh_backend.capacity_min_lines(opts)
            wait_s = dsh_backend.capacity_wait_seconds(opts)
            patch = result.artifacts.get('finalize', {}).get('result', {})
            changed = patch.get('added_lines', 0) + patch.get('removed_lines', 0)
            if patch.get('status') == isolation.APPLY_ERROR:
                return EXIT_FAIL
            if changed < threshold:
                if browser:
                    return EXIT_FAIL
                position = cfg.order.index(selected.name)
                tail = replace(cfg, order=cfg.order[position + 1:])
                return (cmd_managed_run(tail, replace_args(args, _managed_brief=brief),
                                        mode='paseo-required') if tail.order else EXIT_ALL_UNAVAILABLE)
            locked_capacity_branch = True
            for _ in range(DSH_CAPACITY_MAX_CONTINUATIONS):
                if wait_s:
                    time.sleep(wait_s)
                result = controller.continue_capacity(result.key, capacity.continuation_prompt(prompt))
                emit_managed_result(result)
                if result.receipt.get('usage_observation', {}).get('capacity_failure') is not True:
                    break
        status = (result.outcome or {}).get('status')
        from .constants import STATUS_EXIT, FALLBACK_STATUSES
        from .backends.base import Status
        try:
            backend_status = Status(status)
        except ValueError:
            return EXIT_FAIL
        if backend_status in FALLBACK_STATUSES and args.backend == 'auto' and not locked_capacity_branch:
            # Old writer is settled/released before fresh ordered managed selection.
            position = cfg.order.index(selected.name)
            tail = replace(cfg, order=cfg.order[position + 1:])
            if not tail.order:
                return EXIT_ALL_UNAVAILABLE
            return cmd_managed_run(tail, replace_args(args, _managed_brief=brief),
                                   mode='paseo-required')
        return STATUS_EXIT.get(backend_status, EXIT_FAIL)
    except (isolation.IsolationError, ValueError):
        print('hand-ext: invalid managed isolation or execution limits', file=sys.stderr)
        return EXIT_USAGE
    except (AdmissionFull, AdmissionConflict) as exc:
        from .execution_admission import admission_diagnostic
        print(json.dumps(admission_diagnostic(exc)), file=sys.stderr)
        return EXIT_PARALLEL_FULL
    except AdmissionDenied:
        return EXIT_ALL_UNAVAILABLE
    except (ExecutionUnresolved, TransportError, StateConflict):
        print('hand-ext: managed execution unresolved; reconcile exact execution, no shell fallback', file=sys.stderr)
        print(f'state-root: {store.root}', file=sys.stderr)
        if 'attempt' in locals():
            latest = records_for(store, attempt.invocation_id)[-1]
            print(f'invocation: {latest.key.invocation_id} attempt: {latest.key.attempt_id} epoch: {latest.key.epoch}', file=sys.stderr)
        return EXIT_FAIL


def replace_args(args, **changes):
    return argparse.Namespace(**dict(vars(args), **changes))


def build_gateway(store, invocation_id):
    """Trusted standalone binding from durable intent plus current effective repo policy."""
    from .execution_worker import ExecutionWorker
    from .paseo_gateway import Gateway
    rows = records_for(store, invocation_id)
    if not rows:
        raise AdmissionDenied('invocation unavailable')
    record = rows[-1]
    checker = FreshPolicy(store)
    if checker(record.invocation, record.attempt) is not True:
        raise AdmissionDenied('invalid durable policy binding')
    cfg = load_config(Path(record.invocation.source_cwd))
    supervisor = ExecutionSupervisor(store)
    admission = AdmissionController(store, supervisor, checker)
    completion = _completion_service(store, supervisor, admission)
    worker = ExecutionWorker(store, supervisor)
    worker._spec(record.invocation, record.attempt, '')
    completion.attach(worker)
    return Gateway(store, admission, worker, invocation_id=invocation_id,
                   max_parallel=cfg.max_parallel,
                   wait_seconds=float(record.invocation.fixed_options['timeout_s']) + 30,
                   completion=completion)
