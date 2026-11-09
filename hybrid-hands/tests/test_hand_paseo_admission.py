"""Three integration-level admission checks using fake process authority."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import parallel
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore, StateConflict, StateCorrupt
from hand_ext.execution_admission import AdmissionController, AdmissionFull, AdmissionConflict, Reservation
from hand_ext.execution_supervisor import ExecutionSupervisor, ProcessIdentity, Quiescence

class Ops:
    stopped = False
    def reconcile(self, identity): return Quiescence(self.stopped, 'fake verified group reaped' if self.stopped else 'fake writer alive', 1)
    def cancel(self, identity, reason): return self.reconcile(identity)

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(parallel, 'pool_root', return_value=self.root/'pool'); self.patch.start(); self.addCleanup(self.patch.stop)
        self.store = ExecutionStore(self.root/'state'); self.ops = Ops()
        self.supervisor = ExecutionSupervisor(self.store,self.ops)
        self.admission = AdmissionController(self.store,self.supervisor,lambda i,a: True)
    def intent(self, name, scope=None, claims=(), epoch=1):
        i = Invocation(name, scope or parallel.scope_digest(self.root), 'parent', source_cwd=str(self.root), resource_claims=claims)
        return i, Attempt(name, 'attempt'+str(epoch), epoch, name+str(epoch))
    def test_mixed_pool_scopes_and_cap(self):
        i,a = self.intent('managed')
        with parallel.reserve_slot(self.root,3):
            self.admission.admit(i,a,max_parallel=3)
            ni,na = self.intent('native')
            self.admission.reconcile_legacy([dict(invocation=ni,attempt=na)])
            with self.assertRaises(parallel.ParallelFull):
                with parallel.reserve_slot(self.root,3): pass
            with self.assertRaises(AdmissionFull): self.admission.admit(*self.intent('full'),max_parallel=3)
            self.admission.admit(*self.intent('other',scope='independent'),max_parallel=1)
        for invalid in (0,5,True):
            with self.assertRaises(ValueError): self.admission.admit(i,a,max_parallel=invalid)
    def test_not_admitted_and_legacy_intent(self):
        from hand_ext.paseo_recovery import recover
        from hh_ps.paseo_source import load_executions
        from dataclasses import asdict
        i, a = self.intent('holding', claims=('file:shared.py',))
        reservation = self.admission.admit(i, a, max_parallel=1)
        for name, claims, error in (('full', (), AdmissionFull), ('conflict', ('file:shared.py',), AdmissionConflict)):
            inv, attempt = self.intent(name, claims=claims)
            with self.assertRaises(error) as caught: self.admission.admit(inv, attempt, max_parallel=1)
            self.assertEqual(caught.exception.holding_key, a.key)
            self.assertEqual(self.store.get(attempt.key).state, 'not_admitted')
        self.assertTrue(all(r.status != 'unknown' for r in load_executions([self.store.root], 0) if r.exit_code == 8))
        inv, attempt = self.intent('legacy')
        self.store.create_intent(inv, attempt)
        def run(apply=False): return recover(self.store, attempt.key, self.root, None,
            legacy_attest=True, reason='operator checked', apply=apply)
        path = self.store._path(attempt.key); before = path.read_bytes()
        run(); self.assertEqual(path.read_bytes(), before)
        from hand_ext.execution_state import atomic_json
        interrupted = Reservation('interrupted', attempt.key, inv.scope_id, (), str(self.store.root))
        pool = parallel.pool_scope(inv.scope_id)/'reservation-interrupted.json'
        atomic_json(pool, asdict(interrupted))
        with self.assertRaises(StateConflict): run(True)
        self.assertEqual(path.read_bytes(), before); pool.unlink()
        r = self.store.get(attempt.key); r.receipt = {'transport': {'pending':'create'}}
        self.store.compare_and_swap(attempt.key, r.revision, r)
        with self.assertRaises(StateConflict): run(True)
        r = self.store.get(attempt.key); r.receipt = None
        self.store.compare_and_swap(attempt.key, r.revision, r)
        self.assertEqual(run(True).state, 'not_admitted')
        before = path.read_bytes(); run(True); self.assertEqual(path.read_bytes(), before)

    def test_frontend_death_retains_writer_until_authoritative_reap(self):
        i,a = self.intent('writer'); reservation = self.admission.admit(i,a,max_parallel=1)
        self.supervisor.register_writer(a.key,ProcessIdentity(123,123,'owned-start'),'worker')
        # A fresh frontend/store does not reclaim a durable reservation.
        restarted = AdmissionController(ExecutionStore(self.root/'state'),self.supervisor,lambda i,a: True)
        self.assertFalse(self.supervisor.cancel(a.key,'frontend EOF').confirmed)
        with self.assertRaises(AdmissionFull): restarted.admit(*self.intent('blocked'),max_parallel=1)
        outcome = self.supervisor.record_outcome_once(a.key,dict(status='cancelled',quiescent=True))
        self.assertIsNone(outcome.outcome)
        self.assertFalse(outcome.pending_outcome['quiescent'])
        with self.assertRaises(AdmissionConflict): restarted.release(reservation,outcome=outcome.outcome,artifacts_settled=True)
        self.ops.stopped = True
        final = self.supervisor.record_outcome_once(a.key,outcome.pending_outcome)
        self.assertTrue(final.outcome['quiescent'])
        restarted.release(reservation,outcome=final.outcome,artifacts_settled=True)
        restarted.admit(*self.intent('after-reap'),max_parallel=1)
    def test_duplicate_epochs_cas_claims_and_corrupt_fail_closed(self):
        i,a = self.intent('one',claims=('file:shared.py',))
        reservation = self.admission.admit(i,a,max_parallel=4)
        self.assertEqual(reservation,self.admission.admit(i,a,max_parallel=4))
        with self.assertRaises(AdmissionConflict): self.admission.admit(i,Attempt('one','next',2,'next-key'),max_parallel=4)
        with self.assertRaises(AdmissionConflict): self.admission.admit(*self.intent('two',scope='other',claims=('file:shared.py',)),max_parallel=4)
        record = self.store.get(a.key)
        bound = self.store.bind_placement(a.key,record.revision,{'agent_id':'fixed'})
        with self.assertRaises(StateConflict): self.store.compare_and_swap(a.key,record.revision,record)
        with self.assertRaises(StateConflict): self.store.bind_placement(a.key,bound.revision,{'agent_id':'other'})
        with self.assertRaises(AdmissionConflict): self.admission.admit(*self.intent('wide',scope='third',claims=('repo:*',)),max_parallel=4)
        with self.assertRaises(ValueError): parallel.pool_scope('../escape')
        options = {'nested':[1]}; frozen = Invocation('immutable','scope','parent',fixed_options=options)
        options['nested'].append(2)
        self.assertEqual(frozen.fixed_options['nested'],(1,))
        self.store._path(a.key).write_text('{broken')
        with self.assertRaises(StateCorrupt): self.store.get(a.key)

if __name__ == '__main__': unittest.main()
