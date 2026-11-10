"""operator_reconcile: settle a dead writer with sticky incomplete containment (fake OS/Paseo)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import parallel
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore, StateConflict
from hand_ext.execution_admission import AdmissionController
from hand_ext.execution_supervisor import ExecutionSupervisor, ProcessIdentity
from hand_ext.paseo_completion import CompletionService
from hand_ext.post_hoc_reverify import bindings
from hand_ext.process_containment import OSIdentity
from hand_ext.operator_reconcile import (recover_unresolved, OperatorSupervisor, STICKY_EVIDENCE,
                                         ReconcilePlan, AGENT_PROBE_COMMAND)
from hand_ext.execution_worker import ExecutionWorker

UID = os.getuid()
ROOT_PID, DIAG_PID, OTHER_PID = 37664, 42185, 900


class Table:
    """Fake OS: writer pids gone/reused, one unrelated live process."""
    def __init__(self, marker=False, unreadable=False, owner_alive=False):
        self.marker, self.unreadable, self.owner_alive = marker, unreadable, owner_alive
        self.other = OSIdentity(OTHER_PID, 'other-start', 'zsh', 1, UID)
    def identity(self, pid):
        if pid == DIAG_PID: return OSIdentity(pid, 'reused-start', 'x', 1, UID)
        if pid == os.getpid() and self.owner_alive: return OSIdentity(pid, 'owner-start', 'py', 1, UID)
        return self.other if pid == OTHER_PID else None
    def snapshot(self): return {OTHER_PID: self.other}
    def group_present(self, pgid): return False
    def marker_matches(self, pid, invocation):
        if self.unreadable: raise RuntimeError('marker scan unavailable')
        return self.marker


class Sinks(CompletionService):
    """Settlement sinks are out of scope; release path stays official."""
    def _finalize(self, *a): return {}
    _report = _ledger = _go_ledger = _usage_state = _finalize
    def _recover_refs(self, r, kind, token): return {}
    def _after_release(self, key): pass


def completion(store):
    supervisor = OperatorSupervisor(store)
    worker = ExecutionWorker(store, supervisor)
    return Sinks(store, supervisor, AdmissionController(store, supervisor, None)).attach(worker)


class OperatorReconcileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        p = patch.object(parallel, 'pool_root', return_value=self.root / 'pool'); p.start(); self.addCleanup(p.stop)
        self.store = ExecutionStore(self.root / 'state')
        i = Invocation('inv', parallel.scope_digest(self.root), 'parent', parent_paseo_agent_id='parent-agent',
                       source_cwd=str(self.root))
        a = Attempt('inv', 'att', 1, 'req', target_key='tk', project_id='p', workspace_id='ws', agent_id='ag')
        AdmissionController(self.store, ExecutionSupervisor(self.store), lambda i, a: True).admit(i, a, max_parallel=1)
        self.key = a.key
        ExecutionSupervisor(self.store).register_writer(a.key, ProcessIdentity(ROOT_PID, ROOT_PID, 's'), 'worker')
        r = self.store.get(a.key)
        r.receipt = dict(worker_owner='owner', completion=dict(version=1), worker_run_dir=str(self.root / 'run'),
                         transport=dict(agentId='ag'))
        r.receipt['containment'] = dict(
            binding=bindings(r), inventory_complete=False, root_reaped=True,
            root=dict(pid=ROOT_PID, start='root-start', comm='codex', ppid=1, uid=UID),
            owner=dict(pid=os.getpid(), start='owner-start', comm='py', ppid=1, uid=UID),
            inventory=[dict(pid=ROOT_PID, start='root-start', comm='codex', ppid=1, uid=UID)],
            diagnostics=[dict(stage='marker', error='unavailable', pid=DIAG_PID, start='old-start')],
            first_fatal=dict(stage='marker', error='unavailable', pid=DIAG_PID, start='old-start'))
        r.quiescence = dict(confirmed=False, evidence=STICKY_EVIDENCE, observed_at=1.0, details={})
        r.pending_outcome = dict(status='ok', backend_exit_code=0, quiescent=False)
        r.state = 'unresolved'
        self.store.compare_and_swap(a.key, r.revision, r)
        self.pool = next((self.root / 'pool').rglob('reservation-*.json'))

    def run_(self, table, status='closed', **kw):
        probe = lambda req: dict(ok=True, targetKey='tk', agentId='ag', workspaceId='ws', status=status,
                                 archived=True, parentLabel='absent') if req['command'] == AGENT_PROBE_COMMAND else None
        return recover_unresolved(self.store, self.store.get(self.key), table=table, probe=probe,
                                  clock=lambda: 5.0, completion_factory=completion, **kw)

    def test_dead_writer_settles_and_releases_idempotently(self):
        before = self.store.get(self.key).revision
        plan = self.run_(Table())
        self.assertIsInstance(plan, ReconcilePlan)
        self.assertTrue(plan.eligible, plan.blocked)
        self.assertEqual(plan.evidence['owner'], 'absent')
        self.assertEqual(self.store.get(self.key).revision, before)
        done = self.run_(Table(), apply=True, reason='writer dead, agent closed')
        self.assertIsNone(done.reservation)
        self.assertEqual(done.state, 'awaiting_review')
        self.assertEqual(done.outcome['provenance'], 'operator_reconcile')
        self.assertEqual(done.outcome['status'], 'ok')
        self.assertTrue(done.outcome['quiescent'])
        self.assertIsNone(done.pending_outcome)
        self.assertFalse(done.receipt['containment']['inventory_complete'])
        self.assertFalse(self.pool.exists())
        again = self.run_(Table(), apply=True, reason='writer dead, agent closed')
        self.assertEqual(again.revision, done.revision)

    def test_live_marker_or_unreadable_env_blocks_without_writing(self):
        raw = self.store._path(self.key).read_bytes()
        for table in (Table(marker=True), Table(unreadable=True)):
            with self.subTest(marker=table.marker):
                self.assertFalse(self.run_(table).eligible)
                with self.assertRaises(StateConflict):
                    self.run_(table, apply=True, reason='r')
                self.assertEqual(self.store._path(self.key).read_bytes(), raw)
        with self.assertRaises(StateConflict):
            self.run_(Table(), apply=True, reason='  ')
        self.assertEqual(self.store._path(self.key).read_bytes(), raw)

    def test_open_agent_or_live_owner_blocks(self):
        for table, status in ((Table(), 'running'), (Table(owner_alive=True), 'closed')):
            with self.subTest(status=status, owner=table.owner_alive):
                plan = self.run_(table, status=status)
                self.assertFalse(plan.eligible)
                with self.assertRaises(StateConflict):
                    self.run_(table, status=status, apply=True, reason='r')
                self.assertIsNotNone(self.store.get(self.key).reservation)
                self.assertTrue(self.pool.exists())
        def broken(_): raise TimeoutError('bridge timeout')
        plan = recover_unresolved(self.store, self.store.get(self.key), table=Table(), probe=broken)
        self.assertEqual((plan.eligible, plan.blocked), (False, 'exact agent status unavailable'))


def setUpModule():  # keep hh-store revision bumps out of the real ~/.hybrid-hands
    global _STATE_TMP, _STATE_ENV
    _STATE_TMP = tempfile.TemporaryDirectory()
    _STATE_ENV = patch.dict(os.environ, {"HYBRID_HANDS_STATE_DIR": _STATE_TMP.name})
    _STATE_ENV.start()


def tearDownModule():
    _STATE_ENV.stop()
    _STATE_TMP.cleanup()


if __name__ == '__main__':
    unittest.main()
