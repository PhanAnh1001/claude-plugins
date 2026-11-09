"""Offline ACP contract with real durable admission and synthetic worker."""
import io
import json
import queue
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
        self.supervisor.process_ops.stopped = True
        self.supervisor.record_outcome_once(key, dict(status='ok', backend_exit_code=0,
            provenance='fixture', final_text='Synthetic answer', usage={'input':2,'cached_input':1,'output':1}))
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

    def test_initialize_new_prompt_and_authoritative_outcome(self):
        response = self.gateway.handle('initialize',{'protocolVersion':1})
        self.assertTrue(response['agentCapabilities']['loadSession'])
        self.assertEqual(self.gateway.handle('session/new',self.session())['sessionId'],self.invocation.invocation_id)
        emitted = []; self.gateway.emit = emitted.append
        result = self.gateway.handle('session/prompt', self.prompt())
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
