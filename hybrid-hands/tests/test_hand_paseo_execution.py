"""Offline worker ownership/settlement contract; no real CLI, auth or daemon."""
import dataclasses
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import parallel
from hand_ext.backends.base import Status, Usage
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore, StateConflict
from hand_ext.execution_admission import AdmissionController, AdmissionDenied, AdmissionFull
from hand_ext.execution_supervisor import ExecutionSupervisor, Quiescence, ProcessIdentity
from hand_ext.execution_worker import ExecutionWorker


class FakeBackend:
    BLOCKED_ENV = ('FAKE_SECRET',)
    def __init__(self, code): self.code = code
    def build_command(self, spec):
        return [sys.executable, '-c', self.code], {}, spec.prompt
    def parse_line(self, line, state):
        event = json.loads(line)
        state.usage = Usage(input=event['input'], output=event['output'])
        state.final_text = event.get('final', '')
    def poll(self, spec, state): pass
    def finalize(self, spec, state, exit_code, stderr):
        return Status.OK if exit_code == 0 else Status.FAILED


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        # Synthetic fixture runs never inspect environments of other processes.
        scan = patch('hand_ext.process_containment.ProcessTable.marker_matches', return_value=False)
        scan.start(); self.addCleanup(scan.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.isolated = self.root / 'isolated'; self.isolated.mkdir()
        self.pool = patch.object(parallel, 'pool_root', return_value=self.root / 'pool')
        self.pool.start(); self.addCleanup(self.pool.stop)
        self.addCleanup(self.temp.cleanup)
        self.store = ExecutionStore(self.root / 'state')
        self.supervisor = ExecutionSupervisor(self.store)
        self.admission = AdmissionController(self.store, self.supervisor, lambda *_: True)

    def intent(self, name='one', account_alias='gpt', **options):
        fixed = dict(run_dir=str(self.root / ('run-'+name)), sandbox='workspace-write', timeout_s=3, max_tokens=100)
        fixed.update(options)
        invocation = Invocation(name, parallel.scope_digest(self.source), 'parent', backend='codex',
                                account_alias=account_alias, model='fake-fixed', effort='low', source_cwd=str(self.source),
                                isolated_cwd=str(self.isolated), fixed_options=fixed)
        attempt = Attempt(name, 'attempt', 1, 'request-'+name)
        self.store.create_intent(invocation, attempt)
        return invocation, attempt

    def wait(self, predicate, timeout=6):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if predicate(): return
            time.sleep(.01)
        self.fail('bounded wait expired')

    def test_actual_runner_preserves_prepared_dirty_context_settles_once(self):
        baseline = self.isolated / 'dirty'; baseline.write_text('uncommitted baseline')
        calls = []
        def hook(kind):
            def run(key, token, record, outcome):
                self.assertTrue(outcome.quiescent)
                self.assertEqual(record.invocation.isolated_cwd, str(self.isolated))
                self.assertEqual(baseline.read_text(), 'uncommitted baseline')
                calls.append((kind, token, record.attempt.agent_id))
                return {'ref': kind}
            return run
        worker = ExecutionWorker(self.store, self.supervisor,
                                 settlement_hooks={k: hook(k) for k in ('patch','report','ledger')})
        inv, attempt = self.intent()
        self.admission.admit(inv, attempt, max_parallel=1)
        r = self.store.get(attempt.key)
        self.store.bind_placement(attempt.key, r.revision, {'agent_id': 'latest-agent'})
        code = "from pathlib import Path; import json,os; assert 'FAKE_SECRET' not in os.environ; Path('written').open('a').write('patch'); print(json.dumps({'input':4,'output':2,'final':'assistant answer'}))"
        with patch('hand_ext.execution_worker.get_backend', return_value=FakeBackend(code)), patch.dict('os.environ', {'FAKE_SECRET':'fake', parallel.HAND_SCOPE_ENV:'different-daemon-scope'}):
            self.assertNotEqual(inv.scope_id, parallel.scope_digest(self.source))
            starts = []; gate = threading.Barrier(2)
            def start():
                gate.wait(2)
                starts.append(worker.start(inv, attempt, 'brief'))
            threads = [threading.Thread(target=start) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(2)
            self.assertEqual(len(starts), 2)
            self.assertEqual(starts[0].owner_id, starts[1].owner_id)
            first = starts[0]
            self.wait(lambda: len(self.store.get(attempt.key).artifacts) == 3)
            self.assertEqual(worker.start(inv, attempt, 'brief').owner_id, first.owner_id)
            for _ in range(2): worker.reconcile(attempt.key)
        out = worker.outcome(attempt.key)
        self.assertEqual((out.status, out.backend_exit_code, out.usage['input']), ('ok', 0, 4))
        self.assertEqual(out.final_text, 'assistant answer')
        self.assertEqual([x[0] for x in calls], ['patch','report','ledger'])
        self.assertTrue(all(x[2] == 'latest-agent' for x in calls))
        self.assertEqual(len(set(x[1] for x in calls)), 3)
        self.assertEqual((self.isolated / 'written').read_text(), 'patch')
        self.assertEqual(self.store.get(attempt.key).state, 'settling')
        self.assertIsNotNone(self.store.get(attempt.key).reservation)
        self.assertEqual(self.store.get(attempt.key).invocation.scope_id, inv.scope_id)
        self.assertEqual(self.store.get(attempt.key).reservation['scope_id'], inv.scope_id)

    def test_admission_fixed_options_and_runtime_caps(self):
        inv, attempt = self.intent('blocked')
        worker = ExecutionWorker(self.store, self.supervisor)
        with self.assertRaises(StateConflict): worker.start(inv, attempt, '')
        mismatched, mismatched_attempt = self.intent('account-mismatch', account_alias='dsh')
        with self.assertRaisesRegex(ValueError, 'fixed account must match backend'):
            worker.start(mismatched, mismatched_attempt, '')
        with self.assertRaises(AdmissionDenied):
            AdmissionController(self.store, self.supervisor, lambda *_: False).admit(inv, attempt, max_parallel=1)
        self.admission.admit(inv, attempt, max_parallel=1)
        inv2, attempt2 = self.intent('slot')
        with self.assertRaises(AdmissionFull): self.admission.admit(inv2, attempt2, max_parallel=1)
        bad, bad_attempt = self.intent('invalid', unsupported=True)
        self.admission.admit(bad, bad_attempt, max_parallel=4)
        with self.assertRaises(ValueError): worker.start(bad, bad_attempt, '')
        for name, overrides, code, expected in (
            ('tokens', {'max_tokens':1}, "import subprocess,sys,json,time; subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(10)']); print(json.dumps({'input':4,'output':2}),flush=True); time.sleep(10)", 'capped'),
            ('time', {'timeout_s':.05}, 'import time; time.sleep(10)', 'timeout')):
            with self.subTest(name=name):
                invocation, att = self.intent(name, **overrides)
                self.admission.admit(invocation, att, max_parallel=4)
                with patch('hand_ext.execution_worker.get_backend', return_value=FakeBackend(code)):
                    worker.start(invocation, att, '')
                    self.wait(lambda: worker.outcome(att.key) is not None)
                self.assertEqual(worker.outcome(att.key).status, expected)
                self.assertTrue(worker.outcome(att.key).quiescent)

    def test_cancel_restart_lost_ack_and_ambiguous_hook_never_replay(self):
        inv, attempt = self.intent()
        self.admission.admit(inv, attempt, max_parallel=1)
        entered = threading.Event(); finish = threading.Event(); launches = []; calls = []
        identity = ProcessIdentity(123456, 123456, 'fake-owned-generation')
        class Ops:
            def reconcile(self, _): return Quiescence(finish.is_set(), 'fake authoritative group evidence', time.time())
            def cancel(self, _, reason): return self.reconcile(_)
        self.supervisor.process_ops = Ops()
        def runner(backend, spec, control):
            launches.append('launch')
            self.supervisor.register_writer(attempt.key, identity, control.owner)
            entered.set()
            raise RuntimeError('fake crash/lost ACK')
        def interrupted_hook(*args):
            calls.append(args[1]); raise RuntimeError('sink ACK lost after external write')
        worker = ExecutionWorker(self.store, self.supervisor, runner, {'ledger': interrupted_hook})
        handle = worker.start(inv, attempt, '')
        self.assertTrue(entered.wait(2))
        self.assertEqual(worker.start(inv, attempt, '').owner_id, handle.owner_id)
        # A second worker after restart has no authority to replay the launch.
        recovered = ExecutionWorker(self.store, ExecutionSupervisor(self.store), runner)
        self.assertEqual(recovered.start(inv, attempt, '').owner_id, handle.owner_id)
        self.wait(lambda: self.store.get(attempt.key).pending_outcome is not None)
        self.assertFalse(worker.cancel(attempt.key, 'cancel').confirmed)
        self.assertIsNone(worker.outcome(attempt.key)); self.assertEqual(calls, [])
        self.assertIsNotNone(self.store.get(attempt.key).reservation)
        finish.set()
        self.wait(lambda: bool(self.store.get(attempt.key).pending_outcome) or worker.outcome(attempt.key) is not None)
        worker.reconcile(attempt.key)
        self.assertEqual(worker.outcome(attempt.key).backend_exit_code, None)
        self.assertIsNone(worker.outcome(attempt.key).usage)
        for _ in range(2): worker.reconcile(attempt.key)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(launches), 1)
        self.assertEqual(self.store.get(attempt.key).settle_keys['ledger']['state'], 'in_progress')
        self.assertEqual(self.store.get(attempt.key).state, 'settling')


if __name__ == '__main__': unittest.main()
