"""Offline ACP contract with real durable admission and synthetic worker."""
import io
import hashlib
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import parallel
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore
from hand_ext.execution_admission import AdmissionController, Reservation, AdmissionFull
from hand_ext.execution_supervisor import ExecutionSupervisor, ProcessIdentity, Quiescence
from hand_ext.paseo_gateway import Gateway, ProtocolError


class Ops:
    stopped = False
    def reconcile(self, identity):
        return Quiescence(self.stopped, 'synthetic group reaped' if self.stopped else 'synthetic alive', time.time())
    def cancel(self, identity, reason):
        return self.reconcile(identity)


class Worker:
    def __init__(self, store, supervisor, admission):
        self.store, self.supervisor, self.admission = store, supervisor, admission
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.calls = 0
        self.complete = True
    def start(self, invocation, attempt, brief):
        self.calls += 1
        self.supervisor.register_writer(attempt.key, ProcessIdentity(111,111,'synthetic'), 'fixture')
        self.started.set()
        if self.complete:
            self.finish(attempt.key)
    def finish(self, key):
        self.publish(key)
        self.settle(key)
    def publish(self, key):
        self.supervisor.process_ops.stopped = True
        self.supervisor.record_outcome_once(key, dict(status='ok', backend_exit_code=0,
            provenance='fixture', final_text='Synthetic answer', usage={'input':2,'cached_input':1,'output':1}))
    def settle(self, key):
        record = self.store.get(key)
        record.settle_keys = {'report': {'state':'completed','key':'synthetic'}}
        record.artifacts = {'report':'synthetic-report'}
        self.store.compare_and_swap(key, record.revision, record)
        record = self.store.get(key)
        self.admission.release(Reservation.from_dict(record.reservation), outcome=record.outcome, artifacts_settled=True)
    def cancel(self, key, reason):
        self.cancelled.set()
        return self.supervisor.cancel(key, reason)


class Input:
    def __init__(self): self.lines = queue.Queue()
    def __iter__(self): return self
    def __next__(self):
        line = self.lines.get(timeout=3)
        if line is None: raise StopIteration
        return line
    def send(self, method, params, ident=None):
        item = dict(jsonrpc='2.0',method=method,params=params)
        if ident is not None: item['id'] = ident
        self.lines.put(json.dumps(item)+'\n')


class GatewayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        patcher = patch.object(parallel,'pool_root',return_value=self.root/'pool')
        patcher.start(); self.addCleanup(patcher.stop)
        self.store = ExecutionStore(self.root/'state')
        self.ops = Ops(); self.supervisor = ExecutionSupervisor(self.store,self.ops)
        self.checks = []
        self.admission = AdmissionController(self.store,self.supervisor,lambda i,a: self.checks.append(a.key) or True)
        self.key = str(uuid.uuid4())
        self.invocation = Invocation('fixed-invocation',parallel.scope_digest(self.root),'parent',
            backend='codex', account_alias='codex',model='fixed-model',effort='low',
            source_cwd=str(self.root),isolated_cwd=str(self.root),fixed_options={'sandbox':'fixed'})
        self.attempt = Attempt(self.invocation.invocation_id,'initial',1,self.key)
        self.store.create_intent(self.invocation,self.attempt)
        record = self.store.get(self.attempt.key)
        self.store.bind_placement(record.key,record.revision,{'agent_id':'fixed-agent','workspace_id':'fixed-workspace'})
        self.worker = Worker(self.store,self.supervisor,self.admission)
        self.gateway = self.new_gateway()
    def new_gateway(self):
        return Gateway(self.store,self.admission,self.worker,invocation_id=self.invocation.invocation_id,wait_seconds=.5)
    def prompt(self,key=None):
        return dict(sessionId=self.invocation.invocation_id,messageId=key or self.key,
                    prompt=[{'type':'text','text':'Self-contained synthetic brief'}])
    def session(self):
        return dict(sessionId=self.invocation.invocation_id,cwd=str(self.root),mcpServers=[])

    def test_canonical_pinned_envelope(self):
        from hand_ext.paseo_prompt import project, prompt_path, escape, trim
        from hand_ext.execution_state import StateConflict
        r = self.store.get(self.attempt.key)
        r.invocation = replace(r.invocation, fixed_options={'run_dir': str(self.root/'runs')}, parent_paseo_agent_id='parent')
        pin = "\ufeff<&\"'>\n"
        path = prompt_path(r); path.parent.mkdir(parents=True); path.write_bytes(pin.encode())
        r.attempt = replace(r.attempt,target_key='t',project_id='p')
        r.receipt = {'transport': dict(messageId=self.key,briefDigest=hashlib.sha256(pin.encode()).hexdigest(),
            targetKey='t',projectId='p',workspaceId=r.attempt.workspace_id,agentId=r.attempt.agent_id)}
        envelope = ('<paseo-system version="1" kind="agent-message" source-agent-id="' +
                    escape(r.invocation.parent_paseo_agent_id) + '" message-id="' + self.key +
                    '">\n' + escape(trim(pin)) + '\n</paseo-system>')
        self.assertEqual(project(r, envelope, self.key), pin)
        self.assertEqual(project(r, pin, self.key), pin)
        for receipt in ({}, {'brief_digest': None}, {'brief_digest': 'bad'},
                        {'brief_digest': None, **r.receipt}):
            with self.assertRaises(StateConflict): project(replace(r,receipt=receipt), pin, self.key)
        partial=replace(r,attempt=replace(r.attempt,target_key=None))
        with self.assertRaises(StateConflict): project(partial,envelope,self.key)
        self.assertEqual(trim('\u0085x\u001c'), '\u0085x\u001c')
        for bad in (envelope.replace(self.key, str(uuid.uuid4())),
                    envelope.replace('source-agent-id="parent"', 'source-agent-id="other"'),
                    envelope+'\n'+envelope, envelope+'prose',
                    envelope.replace('&lt;', '&#60;'), envelope.replace('&gt;', 'x')):
            with self.subTest(bad=bad), self.assertRaises(StateConflict): project(r, bad, self.key)

    def test_unbound_discovery_and_partial_binding(self):
        from hand_ext.paseo_gateway import main
        requests = [('initialize', {'protocolVersion': 1}), ('session/new', {})]
        requests += [(method, {}) for method in ('session/prompt', 'session/cancel', 'session/close', 'session/load', 'session/set_model')]
        source = io.StringIO(''.join(json.dumps(dict(jsonrpc='2.0', id=i, method=m, params=p))+'\n' for i,(m,p) in enumerate(requests)))
        sink = io.StringIO()
        with patch.dict('os.environ', {}, clear=True), patch('sys.stdin', source), patch('sys.stdout', sink), patch('hand_ext.paseo_gateway.ExecutionStore', side_effect=AssertionError('store constructed')):
            self.assertEqual(main([]), 0)
            with patch('sys.stderr', io.StringIO()):
                for root, invocation in (('/fake', None), (None, 'fake'), ('', None), (None, ''), ('', '')):
                    bindings = {key: value for key, value in zip(('HYBRID_HANDS_EXECUTION_ROOT', 'HYBRID_HANDS_INVOCATION_ID'), (root, invocation)) if value is not None}
                    for argv, env in (([], bindings), ([arg for flag, value in zip(('--state-root', '--invocation-id'), (root, invocation)) if value is not None for arg in (flag, value)], {})):
                        with patch.dict('os.environ', env, clear=True), patch('sys.stdout', io.StringIO()) as rejected:
                            with self.assertRaises(SystemExit) as error: main(argv)
                            self.assertEqual(error.exception.code, 2)
                            self.assertEqual(rejected.getvalue(), '')
        rows = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(rows[0]['result']['agentCapabilities'], {})
        self.assertEqual(rows[1]['result']['models']['currentModelId'], 'default')
        self.assertEqual([r['error'] for r in rows[2:]], [{'code': -32003, 'message': 'discovery only; execution binding required'}]*5)

    def test_bound_metadata_skips_paseo_overrides(self):
        executable = shutil.which('paseo')
        if not executable: self.skipTest('Paseo CLI 0.15.0 unavailable')
        package = Path(executable).resolve().parent
        while package.parent != package and not (package/'package.json').is_file():
            package = package.parent
        manifest = package/'package.json'
        identity = json.loads(manifest.read_text()) if manifest.is_file() else {}
        if (identity.get('name'), identity.get('version')) != ('@getpaseo/cli', '0.15.0'):
            self.skipTest('compatible @getpaseo/cli 0.15.0 unavailable')
        module = package/'node_modules/@getpaseo/server/dist/server/server/agent/providers/acp-agent.js'
        if not module.is_file(): self.skipTest('pinned public Paseo source unavailable')
        script = """const {ACPAgentSession}=await import(process.argv[1]);
          let text='';for await(const chunk of process.stdin)text+=chunk;const session=Object.create(ACPAgentSession.prototype);
          Object.assign(session,{config:{modeId:'default',model:'fixed-model',thinkingOptionId:'low'},configFeatureOptions:[],defaultModes:[]});
          session.applySessionState(JSON.parse(text));await session.applyConfiguredOverrides();console.log(JSON.stringify([session.currentMode,session.currentModel,session.thinkingOptionId]));"""
        for method in ('session/new', 'session/load'):
            metadata = self.gateway.handle(method, self.session())
            run = subprocess.run(['node', '--input-type=module', '-e', script, module.as_uri()], input=json.dumps(metadata), capture_output=True, text=True, timeout=10)
            self.assertEqual((run.returncode, json.loads(run.stdout or 'null')), (0, ['default', 'fixed-model', 'low']), run.stderr)
        self.assertEqual((self.worker.calls, self.checks), (0, []))

    def test_initialize_new_prompt_and_authoritative_outcome(self):
        response = self.gateway.handle('initialize',{'protocolVersion':1})
        self.assertTrue(response['agentCapabilities']['loadSession'])
        self.assertEqual(self.gateway.handle('session/new',self.session())['sessionId'],self.invocation.invocation_id)
        emitted = []; self.gateway.emit = emitted.append
        self.worker.complete = False
        results, errors = [], []
        finished = threading.Event()
        def prompt():
            try:
                results.append(self.gateway.handle('session/prompt', self.prompt()))
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()
        pending = threading.Thread(target=prompt)
        pending.start()
        self.assertTrue(self.worker.started.wait(1))
        self.worker.publish(self.attempt.key)
        try:
            self.assertFalse(finished.wait(.1), 'prompt must wait for settlement/release')
        finally:
            self.worker.settle(self.attempt.key)
            pending.join(1)
        self.assertFalse(pending.is_alive())
        self.assertEqual(errors, [])
        result = results[0]
        self.assertEqual(result['stopReason'],'end_turn')
        self.assertEqual(result['usage'],{'totalTokens':3,'inputTokens':2,'outputTokens':1,'cachedReadTokens':1})
        self.assertEqual(emitted[0]['params']['update']['content']['text'],'Synthetic answer')
        record = self.store.get(self.attempt.key)
        self.assertEqual(record.state,'awaiting_review'); self.assertIsNone(record.reservation)
        self.assertEqual(record.attempt.agent_id,'fixed-agent')
        with self.assertRaises(ProtocolError):
            self.gateway.handle('session/new',dict(cwd='/',mcpServers=[]))
        # Explicit backend failure is a protocol error with nullable real exit.
        record.outcome = dict(record.outcome,status='failed',backend_exit_code=9)
        with self.assertRaises(ProtocolError) as error: self.gateway._result(record,self.key)
        self.assertEqual(error.exception.data['backend_exit_code'],9)
        record.state='settling'
        record.outcome = dict(record.outcome,status='ok',backend_exit_code=0)
        with self.assertRaises(ProtocolError): self.gateway._result(record,self.key)
        # A settled backend can still have pending artifacts. Deadline expiry
        # preserves its reservation; attaching again never launches a second writer.
        self.worker.complete = True
        waiting = self.new_gateway(); waiting.wait_seconds = .05
        next_key = str(uuid.uuid4())
        with patch.object(self.worker, 'finish', side_effect=self.worker.publish):
            for _ in range(2):
                with self.assertRaises(ProtocolError) as error:
                    waiting.handle('session/prompt', self.prompt(next_key))
                self.assertEqual(error.exception.data['kind'], 'settlement_pending')
        retained = waiting._records()[-1]
        self.assertTrue(retained.reservation)
        self.assertEqual(self.worker.calls, 2)
        self.worker.settle(retained.key)

    def test_stdio_cancel_and_eof_keep_live_writer_reserved(self):
        self.worker.complete = False
        self.gateway.wait_seconds = 2
        source, sink = Input(), io.StringIO()
        thread = threading.Thread(target=self.gateway.serve,args=(source,sink))
        thread.start()
        source.send('session/prompt',self.prompt(),1)
        self.assertTrue(self.worker.started.wait(1))
        # Fill all eight prompt wait slots with duplicate attachments. Control
        # must retain its independent slot, and none may spawn a second writer.
        for ident in range(3,10):
            source.send('session/prompt',self.prompt(),ident)
        deadline = time.monotonic()+1
        while len(self.checks)<8 and time.monotonic()<deadline: time.sleep(.01)
        self.assertEqual(len(self.checks),8)
        source.send('session/prompt',self.prompt(),10)
        source.send('session/cancel',{'sessionId':self.invocation.invocation_id})
        self.assertTrue(self.worker.cancelled.wait(1))
        source.send('initialize',{'protocolVersion':1},2)
        deadline = time.monotonic()+1
        while '"id": 2' not in sink.getvalue() and time.monotonic()<deadline: time.sleep(.01)
        self.assertIn('"id": 2',sink.getvalue())
        self.assertEqual(self.worker.calls,1)
        busy = [json.loads(line) for line in sink.getvalue().splitlines() if json.loads(line).get('id')==10]
        self.assertEqual(busy[0]['error']['code'],-32009)
        source.lines.put(None); thread.join(2)
        self.assertFalse(thread.is_alive())
        record = self.store.get(self.attempt.key)
        self.assertEqual(record.state,'unresolved'); self.assertTrue(record.reservation)
        self.assertIsNone(record.outcome)
        messages = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertFalse(any(m.get('result',{}).get('stopReason')=='end_turn' for m in messages))
        self.assertFalse(any(m.get('id') is None for m in messages))

    def test_load_duplicates_concurrent_claim_and_followup_epoch(self):
        self.worker.complete = False
        errors=[]
        def run(gateway):
            try: gateway.handle('session/prompt',self.prompt())
            except ProtocolError as exc: errors.append(exc.code)
        first = threading.Thread(target=run,args=(self.gateway,)); first.start()
        self.assertTrue(self.worker.started.wait(1))
        restarted = self.new_gateway()
        second = threading.Thread(target=run,args=(restarted,)); second.start()
        second.join(1); first.join(1)
        self.assertEqual(self.worker.calls,1)
        history = restarted.handle('session/load',self.session())['_meta']['history']
        self.assertEqual(len(history),1)
        with self.assertRaises(ProtocolError): restarted.handle('session/prompt',self.prompt(str(uuid.uuid4())))
        self.worker.finish(self.attempt.key)
        self.assertEqual(restarted.handle('session/prompt',self.prompt())['stopReason'],'end_turn')
        self.assertEqual(self.worker.calls,1)
        self.worker.complete=True
        next_key=str(uuid.uuid4())
        self.assertEqual(restarted.handle('session/prompt',self.prompt(next_key))['stopReason'],'end_turn')
        records = restarted._records()
        self.assertEqual([r.attempt.epoch for r in records],[1,2])
        self.assertEqual(records[-1].attempt.agent_id,'fixed-agent')
        self.assertIsNone(records[-1].attempt.thread_id)
        self.assertEqual(self.worker.calls,2)
        self.assertGreaterEqual(len(self.checks),4)
        # An unrelated real writer fills the pool. Completed attachment still
        # checks policy and reads the cached outcome, without needing a slot.
        other = replace(self.invocation, invocation_id='other-active')
        other_attempt = Attempt(other.invocation_id,'other-attempt',1,str(uuid.uuid4()))
        self.admission.admit(other,other_attempt,max_parallel=1)
        before = len(self.checks)
        self.assertEqual(restarted.handle('session/prompt',self.prompt(next_key))['stopReason'],'end_turn')
        self.assertEqual(len(self.checks),before+1)
        self.assertEqual(self.worker.calls,2)
        with patch.object(self.admission,'policy_checker',return_value=False):
            with self.assertRaises(ProtocolError) as error:
                restarted.handle('session/prompt',self.prompt(next_key))
        self.assertEqual(error.exception.code,-32003)
        # A new request still needs capacity and returns the distinct exit 8.
        with self.assertRaises(ProtocolError) as error:
            restarted.handle('session/prompt',self.prompt(str(uuid.uuid4())))
        self.assertEqual(error.exception.data['exit_code'],8)
        self.assertEqual(self.worker.calls,2)

if __name__ == '__main__': unittest.main()
