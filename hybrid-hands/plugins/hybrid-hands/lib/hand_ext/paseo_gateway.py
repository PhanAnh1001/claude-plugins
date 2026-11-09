"""ACP projection of authoritative executions; no policy or runner defaults.

Trusted callers inject AdmissionController and ExecutionWorker and bind an existing
invocation_id. max_parallel must come from trusted policy, never ACP parameters.
The standalone entry intentionally denies prompts until G3 supplies that wiring.
"""
import argparse
import fcntl
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from pathlib import Path

from .execution_state import Attempt, ExecutionStore, StateConflict
from .execution_admission import AdmissionFull, AdmissionConflict, AdmissionDenied


class ProtocolError(Exception):
    def __init__(self, code, message, data=None):
        self.code, self.message, self.data = code, message, data


class Gateway:
    def __init__(self, store, admission, worker, *, invocation_id=None,
                 max_parallel=1, wait_seconds=30, completion=None):
        self.store, self.admission, self.worker = store, admission, worker
        self.completion = completion
        self.invocation_id = invocation_id
        self.max_parallel, self.wait_seconds = max_parallel, wait_seconds
        self.owner = str(uuid.uuid4())
        self.stopping = threading.Event()
        self.owned = set()
        self.cancelled = set()
        self.mutex = threading.RLock()
        self.emit = lambda message: None

    @contextmanager
    def _locked(self):
        # Separate lock: store methods acquire their own lock. Serializes epoch
        # allocation and durable claim across independent gateway processes.
        with (self.store.root / '.gateway-lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _records(self):
        with self.store.locked():
            rows = [self.store._read(p) for p in self.store.root.glob('*.json')]
        rows = [r for r in rows if r.invocation.invocation_id == self.invocation_id]
        if not rows:
            raise ProtocolError(-32004, 'authoritative invocation unavailable')
        return sorted(rows, key=lambda r: r.attempt.epoch)

    def _session(self, params):
        if params.get('sessionId') != self.invocation_id:
            raise ProtocolError(-32602, 'session binding mismatch')
        return self._records()[-1]

    def _cwd(self, params, record):
        cwd = params.get('cwd')
        if not isinstance(cwd, str) or Path(cwd).resolve() != Path(record.invocation.isolated_cwd).resolve():
            raise ProtocolError(-32602, 'cwd binding mismatch')
        if params.get('mcpServers') != []:
            raise ProtocolError(-32602, 'MCP servers unsupported')

    def handle(self, method, params):
        if not isinstance(params, dict):
            raise ProtocolError(-32602, 'invalid parameters')
        if method == 'initialize':
            if params.get('protocolVersion') != 1:
                raise ProtocolError(-32602, 'unsupported protocol version')
            return {'protocolVersion': 1, 'agentCapabilities': {
                'loadSession': True, 'sessionCapabilities': {'close': {}}},
                'agentInfo': {'name': 'hand-paseo-acp', 'version': 'stage1'}}
        if method == 'session/new':
            record = self._records()[-1]
            self._cwd(params, record)
            return {'sessionId': self.invocation_id, **self._metadata(record)}
        if method == 'session/load':
            record = self._session(params)
            self._cwd(params, record)
            # Only durable public outcome metadata, never transcript/auth files.
            return {**self._metadata(record),
                    '_meta': {'history': [self._history(r) for r in self._records()]}}
        if method == 'session/prompt':
            return self._prompt(params)
        if method in ('session/cancel', 'session/close'):
            self._session(params)
            self._cancel('client_cancel' if method.endswith('cancel') else 'session_close')
            return {}
        raise ProtocolError(-32601, 'method unsupported')

    @staticmethod
    def _metadata(record):
        """Project durable selections so ACP need not invoke unsupported setters.

        These singleton choices describe policy; Invocation remains authoritative
        and no model/mode/effort mutation method is exposed.
        """
        invocation = record.invocation
        metadata = {'modes': {'currentModeId': 'default', 'availableModes': [
            {'id': 'default', 'name': 'Bound execution policy'}]}}
        if invocation.model:
            metadata['models'] = {
                'currentModelId': invocation.model, 'availableModels': [
                    {'modelId': invocation.model, 'name': invocation.model}]}
        if invocation.effort:
            metadata['configOptions'] = [{
                'id': 'bound-effort', 'name': 'Bound execution effort',
                'type': 'select', 'category': 'thought_level',
                'currentValue': invocation.effort, 'options': [
                    {'value': invocation.effort, 'name': invocation.effort}]}]
        return metadata

    @staticmethod
    def _history(record):
        outcome = record.outcome or {}
        return {'epoch': record.attempt.epoch, 'requestKey': record.attempt.request_key,
                'state': record.state, 'status': outcome.get('status'),
                'backend_exit_code': outcome.get('backend_exit_code')}

    def _prompt(self, params):
        self._session(params)
        blocks = params.get('prompt')
        if not isinstance(blocks, list) or not blocks or any(
                not isinstance(b, dict) or b.get('type') != 'text' or
                not isinstance(b.get('text'), str) for b in blocks):
            raise ProtocolError(-32602, 'self-contained text prompt required')
        key = params.get('messageId')
        try:
            uuid.UUID(key)
        except (ValueError, TypeError, AttributeError):
            raise ProtocolError(-32602, 'UUID messageId required')
        plaintext = '\n'.join(b['text'] for b in blocks)
        digest = hashlib.sha256(plaintext.encode()).hexdigest()
        claimed = False
        with self._locked():
            rows = self._records()
            existing = next((r for r in rows if r.attempt.request_key == key), None)
            if existing:
                record = existing
                receipt = record.receipt or {}
                if receipt.get('prompt_rejection'):
                    raise ProtocolError(-32602, 'prompt fence rejected')
                if self.completion is not None:
                    from .paseo_prompt import project
                    try:
                        plaintext = project(record, plaintext, key)
                    except (StateConflict, OSError, ValueError, KeyError):
                        # No existing claimant can still be on its way to start().
                        if (not any(k in receipt for k in ('gateway_claim', 'worker_owner', 'worker_run_dir'))
                                and record.writer is None and record.process is None
                                and record.outcome is None and record.pending_outcome is None):
                            record.receipt = dict(receipt, prompt_rejection={
                                'reason': 'gateway_prompt_fence_rejected', 'epoch': record.attempt.epoch,
                                'request_key': key})
                            self.store.compare_and_swap(record.key, record.revision, record)
                        raise ProtocolError(-32602, 'prompt fence rejected') from None
                    digest = hashlib.sha256(plaintext.encode()).hexdigest()
                if receipt.get('brief_digest', digest) != digest:
                    raise ProtocolError(-32602, 'request key content mismatch')
            else:
                if self.completion is not None:
                    raise ProtocolError(-32602, 'dispatcher prompt binding required')
                latest = rows[-1]
                if latest.reservation or latest.writer and not latest.outcome:
                    raise ProtocolError(-32009, 'previous writer unresolved')
                if latest.state not in ('awaiting_review', 'archived', 'failed') and (latest.receipt or latest.outcome):
                    raise ProtocolError(-32009, 'previous attempt unsettled')
                attempt = replace(latest.attempt, attempt_id=str(uuid.uuid4()),
                                  epoch=latest.attempt.epoch + 1, request_key=key,
                                  run_id=None, thread_id=None)
                if self.completion is not None:
                    if (latest.artifacts.get('review') or {}).get('approved') is not True:
                        raise ProtocolError(-32009, 'previous attempt requires review')
                record = self.store.create_intent(latest.invocation, attempt)
                if self.completion is not None:
                    from .paseo_controller import bind_followup
                    record = bind_followup(self.store, latest, record)
            # Fresh policy on every request, including duplicate attachment.
            # Admission uses the latest placement-bound Attempt, never a stale
            # pre-create Attempt with null placement fields.
            try:
                if record.outcome is not None:
                    # Completed attachment is a read, not a new writer. Keep
                    # fresh policy without touching reservations or pool cap.
                    if self.admission.policy_checker(record.invocation, record.attempt) is not True:
                        raise AdmissionDenied('explicit policy allow required')
                else:
                    self.admission.admit(record.invocation, record.attempt,
                                         max_parallel=self.max_parallel)
            except AdmissionFull:
                raise ProtocolError(-32008, 'execution pool full', {'kind': 'admission_full', 'exit_code': 8})
            except AdmissionDenied:
                raise ProtocolError(-32003, 'policy denied or unavailable', {'kind': 'policy_denied', 'exit_code': 7})
            except AdmissionConflict:
                if not record.outcome:
                    raise ProtocolError(-32009, 'execution conflict', {'kind': 'execution_conflict', 'exit_code': 8})
            record = self.store.get(record.key)
            if not record.outcome and not (record.receipt or {}).get('gateway_claim'):
                record.receipt = dict(record.receipt or {}, gateway_claim=self.owner, brief_digest=digest)
                record = self.store.compare_and_swap(record.key, record.revision, record)
                claimed = True
                with self.mutex:
                    self.owned.add(record.key)
        if claimed:
            if self.stopping.is_set():
                raise ProtocolError(-32010, 'gateway stopping; execution retained')
            try:
                if self.completion is not None:
                    from .paseo_controller import persist_prompt
                    persist_prompt(record, plaintext)
                self.worker.start(record.invocation, record.attempt, plaintext)
            except Exception:
                # A failed start may have dispatched a writer. Never retry it.
                raise ProtocolError(-32010, 'worker start unresolved; execution retained')
        deadline = time.monotonic() + self.wait_seconds
        settlement_pending = False
        while time.monotonic() < deadline and not self.stopping.is_set():
            if self.completion is not None:
                observed = self.store.get(record.key)
                if (observed.outcome is not None or observed.pending_outcome is not None) and observed.reservation:
                    # The worker serializes live hooks with this same lock.
                    # Never race an in_progress hook or churn running writer CAS.
                    with getattr(self.worker, 'lock', nullcontext()):
                        self.completion.reconcile(record.key)
            record = self.store.get(record.key)
            if record.outcome and record.outcome.get('quiescent') is True:
                status = record.outcome.get('status')
                successful = status in ('ok', 'completed', 'success', 'succeeded') and record.outcome.get('backend_exit_code') in (None, 0)
                settlement_pending = successful and (
                    record.state not in ('awaiting_review', 'archived') or bool(record.reservation))
                if not settlement_pending:
                    return self._result(record, key)
            with self.mutex:
                cancelled = record.key in self.cancelled
            if cancelled:
                return {'stopReason': 'cancelled', 'userMessageId': key,
                        '_meta': {'status': 'unresolved', 'quiescent': False}}
            self.stopping.wait(.02)
        if settlement_pending:
            raise ProtocolError(-32010, 'outcome pending settlement or release', {'kind': 'settlement_pending'})
        raise ProtocolError(-32010, 'execution unresolved; reservation retained', {'kind': 'unresolved'})

    def _result(self, record, message_id):
        outcome = record.outcome
        status = outcome.get('status')
        code = outcome.get('backend_exit_code')
        meta = {'status': status, 'backend_exit_code': code,
                'provenance': outcome.get('provenance'), 'quiescent': True,
                'epoch': record.attempt.epoch, 'state': record.state}
        if status not in ('ok', 'completed', 'success', 'succeeded', 'cancelled') or code not in (None, 0):
            raise ProtocolError(-32011, 'backend execution failed', meta)
        if status != 'cancelled' and (record.state not in ('awaiting_review', 'archived') or record.reservation):
            raise ProtocolError(-32010, 'outcome pending settlement or release', {'kind': 'settlement_pending', 'status': status})
        text = outcome.get('final_text')
        if isinstance(text, str) and text:
            self.emit({'jsonrpc': '2.0', 'method': 'session/update', 'params': {
                'sessionId': self.invocation_id, 'update': {'sessionUpdate': 'agent_message_chunk',
                'content': {'type': 'text', 'text': text}}}})
        result = {'stopReason': 'cancelled' if status == 'cancelled' else 'end_turn',
                  'userMessageId': message_id, '_meta': meta}
        usage = outcome.get('usage')
        if isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('input', 'output', 'cached_input')):
            usage = {'inputTokens': usage['input'], 'outputTokens': usage['output'],
                     'totalTokens': usage['input'] + usage['output'], 'cachedReadTokens': usage['cached_input']}
        required = ('totalTokens', 'inputTokens', 'outputTokens')
        if isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in required):
            result['usage'] = {k: usage[k] for k in required}
            if type(usage.get('cachedReadTokens')) is int and usage['cachedReadTokens'] >= 0:
                result['usage']['cachedReadTokens'] = usage['cachedReadTokens']
        return result

    def _cancel(self, reason):
        with self.mutex:
            keys = tuple(self.owned)
            if reason != 'gateway_eof':
                keys = tuple(r.key for r in self._records() if r.reservation or r.writer and not r.outcome)
            self.cancelled.update(keys)
        for key in keys:
            record = self.store.get(key)
            if record.outcome and not record.reservation:
                continue
            try:
                self.worker.cancel(key, reason)
            except Exception:
                pass  # No release or fabricated success on cancellation failure.

    def serve(self, source, sink):
        output_lock = threading.Lock()
        threads = []
        control = None
        def emit(message):
            with output_lock:
                sink.write(json.dumps(message, allow_nan=False) + '\n')
                sink.flush()
        self.emit = emit
        def dispatch(request):
            request_id = request.get('id')
            try:
                result = self.handle(request.get('method'), request.get('params', {}))
                response = {'result': result}
            except ProtocolError as exc:
                response = {'error': {'code': exc.code, 'message': exc.message}}
                if exc.data is not None:
                    response['error']['data'] = exc.data
            except Exception:
                response = {'error': {'code': -32603, 'message': 'gateway operation failed safely'}}
            if 'id' in request:
                emit(dict(response, jsonrpc='2.0', id=request_id))
        try:
            for line in source:
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
                        raise ValueError()
                except (ValueError, TypeError):
                    emit({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'invalid JSON-RPC'}})
                    continue
                if request.get('method') in ('session/cancel', 'session/close'):
                    # Control has its own slot: duplicate prompts cannot starve cancel.
                    if control is None or not control.is_alive():
                        control = threading.Thread(target=dispatch, args=(request,), daemon=True)
                        control.start()
                    elif 'id' in request:
                        emit({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32009, 'message': 'cancellation pending'}})
                elif request.get('method') == 'session/prompt':
                    threads = [t for t in threads if t.is_alive()]
                    if len(threads) >= 8:
                        if 'id' in request:
                            emit({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32009, 'message': 'gateway busy'}})
                        continue
                    thread = threading.Thread(target=dispatch, args=(request,), daemon=True)
                    threads.append(thread)
                    thread.start()
                else:
                    dispatch(request)
        finally:
            self.stopping.set()
            # bounded shutdown even if an injected worker cannot confirm stop
            thread = threading.Thread(target=self._cancel, args=('gateway_eof',), daemon=True)
            thread.start()
            deadline = time.monotonic() + 1
            for task in [thread] + threads + ([control] if control else []):
                task.join(max(0, deadline - time.monotonic()))



class DiscoveryGateway(Gateway):
    """Static provider-neutral catalog; deliberately has no execution dependencies.

    Paseo 0.15.0 initialize supplies client identity/capabilities, not provider ID.
    `default` defers model selection to the bound execution and never overrides it.
    No close capability is advertised, so fetchCatalog cleanup closes transport.
    """
    def __init__(self):
        super().__init__(None, None, None)

    def handle(self, method, params):
        if method not in ('initialize', 'session/new'):
            raise ProtocolError(-32003, 'discovery only; execution binding required')
        if not isinstance(params, dict):
            raise ProtocolError(-32602, 'invalid parameters')
        if method == 'initialize':
            if params.get('protocolVersion') != 1:
                raise ProtocolError(-32602, 'unsupported protocol version')
            return {'protocolVersion': 1, 'agentCapabilities': {},
                    'agentInfo': {'name': 'hand-paseo-acp', 'version': 'stage1'}}
        return {'sessionId': 'hand-paseo-discovery',
                'models': {'currentModelId': 'default', 'availableModels': [
                    {'modelId': 'default', 'name': 'Bound execution default'}]},
                'modes': {'currentModeId': 'default', 'availableModes': [
                    {'id': 'default', 'name': 'Bound execution policy'}]}}

    def serve(self, source, sink):
        # Synchronous metadata dispatch: even prompt floods receive the same error.
        for line in source:
            request = None
            try:
                request = json.loads(line)
                if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
                    request = None
                    raise ValueError()
                response = {'result': self.handle(request.get('method'), request.get('params', {}))}
            except (ValueError, TypeError):
                response = {'error': {'code': -32700, 'message': 'invalid JSON-RPC'}}
            except ProtocolError as error:
                response = {'error': {'code': error.code, 'message': error.message}}
            if request is None or 'id' in request:
                sink.write(json.dumps(dict(response, jsonrpc='2.0',
                                           id=request.get('id') if request else None)) + '\n')
                sink.flush()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', default=os.environ.get('HYBRID_HANDS_EXECUTION_ROOT'))
    parser.add_argument('--invocation-id', default=os.environ.get('HYBRID_HANDS_INVOCATION_ID'))
    args = parser.parse_args(argv)
    if args.state_root is None and args.invocation_id is None:
        DiscoveryGateway().serve(sys.stdin, sys.stdout)
        return 0
    if not args.state_root or not args.invocation_id:
        parser.error('explicit state root and invocation id required')
    store = ExecutionStore(args.state_root)
    try:
        from .paseo_controller import build_gateway
        gateway = build_gateway(store, args.invocation_id)
    except Exception:
        # Invalid/missing durable binding has no worker and cannot execute prompts.
        from .execution_admission import AdmissionController
        from .execution_supervisor import ExecutionSupervisor
        supervisor = ExecutionSupervisor(store)
        admission = AdmissionController(store, supervisor, lambda invocation, attempt: False)
        gateway = Gateway(store, admission, None, invocation_id=args.invocation_id)
    gateway.serve(sys.stdin, sys.stdout)
    return 0
