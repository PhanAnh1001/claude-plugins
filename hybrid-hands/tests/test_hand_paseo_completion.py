"""Three offline completion groups using fake runner and disposable git fixtures."""
import json
import dataclasses
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import isolation, parallel
from hand_ext.backends.base import RunState, Usage, Status, Quota
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore, StateConflict
from hand_ext.execution_supervisor import ExecutionSupervisor, Quiescence, ProcessIdentity
from hand_ext.execution_admission import AdmissionController
from hand_ext.execution_worker import ExecutionWorker
from hand_ext import execution_worker
from hand_ext.runner import RunOutcome
from hand_ext.paseo_completion import CompletionService, reconstruct_context


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.iso = self.root / 'worktree'
        def git(*args):
            return subprocess.run(['git', '-C', str(self.source), *args], capture_output=True, text=True, check=True).stdout.strip()
        git('init')
        (self.source / 'fixture').write_text('baseline\n')
        git('add', 'fixture')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
        baseline = git('rev-parse', 'HEAD^{tree}')
        git('worktree', 'add', '--detach', str(self.iso))
        self.baseline = baseline
        pool = patch.object(parallel, 'pool_root', return_value=self.root / 'pool')
        pool.start(); self.addCleanup(pool.stop)
        self.store = ExecutionStore(self.root / 'store')
        self.confirmed = True
        owner = self
        class Ops:
            def reconcile(self, identity): return Quiescence(owner.confirmed, 'fake group reaped', time.time())
        self.supervisor = ExecutionSupervisor(self.store, Ops())
        self.admission = AdmissionController(self.store, self.supervisor, lambda *_: True)
        self.service = CompletionService(self.store, self.supervisor, self.admission)
        self.inv = Invocation('one', parallel.scope_digest(self.source), 'parent', backend='dsh',
                              model='deepseek-v4.1-flash', effort='off', source_cwd=str(self.source), isolated_cwd=str(self.iso),
                              fixed_options=dict(run_dir=str(self.root / 'runs'), sandbox='workspace-write', timeout_s=2, max_tokens=100))
        self.attempt = Attempt('one', 'try', 1, 'request')
        self.admission.admit(self.inv, self.attempt, max_parallel=1)
        self.ctx = isolation.IsolationContext('worktree', self.source, self.iso, self.iso, baseline_tree=self.baseline)
        self.service.bind(self.attempt.key, self.ctx, ledger_path=self.root / 'ledger.json', registry_dir=self.root / 'registry', policy='apply',
                          go_ledger=self.root / 'go.jsonl', go_summary=self.root / 'go-summary.json', go_monthly_limit=10,
                          quota_path=self.root / 'quota.json', label='fixture-label')

    def runner(self, status=Status.OK):
        def run(backend, spec, control):
            self.supervisor.register_writer(self.attempt.key, ProcessIdentity(123456,123456,'fake-owned'), control.owner)
            (self.iso / 'fixture').write_text('changed by fixture\n')
            state = RunState(Usage(10, 2, 4), quota=Quota(5, None), final_text='fixture report', extra={'go_allowance_usd': 0.01})
            return RunOutcome(status, 0 if status == Status.OK else 1, state, 0.1, ['prefill_cap_refused'] if status == Status.FAILED else [])
        return run

    def wait(self, predicate):
        until = time.monotonic() + 3
        while time.monotonic() < until:
            if predicate(): return
            time.sleep(.01)
        self.fail('completion wait expired')

    def finalize(self, ctx, directory, **kwargs):
        self.applies.append(kwargs['apply_changes'])
        p = directory / 'changes.patch'; p.write_text('fake patch')
        return isolation.ApplyResult('applied' if kwargs['apply_changes'] else 'skipped', ['fixture'], p)

    def test_success_runner_finalize_report_ledgers_release_once(self):
        self.applies = []
        fake = self.runner()
        def with_registry(backend, spec, control, registry):
            running = json.loads(registry.path.read_text())
            self.assertEqual(running['status'], 'running')
            self.assertEqual(running['label'], 'fixture-label')
            registry.child(123456)
            registry.tick(Usage(10, 2, 4))
            return fake(backend, spec, control)
        with patch.object(execution_worker, 'run_backend', with_registry):
            worker = ExecutionWorker(self.store, self.supervisor)
        self.service.attach(worker)
        original_cas = self.store.compare_and_swap
        conflicts = []
        def cas(key, revision, record):
            if record.receipt and record.receipt.get('usage_observation') and not record.outcome and not conflicts:
                conflicts.append(True)
                raise StateConflict('fixture transport ACK race')
            return original_cas(key, revision, record)
        real_finalize = isolation.finalize
        def finalize(*args, **kwargs):
            self.applies.append(kwargs['apply_changes'])
            return real_finalize(*args, **kwargs)
        with patch.object(isolation, 'finalize', finalize), patch.object(self.store, 'compare_and_swap', cas):
            worker.start(self.inv, self.attempt, 'public fake brief')
            self.wait(lambda: self.store.get(self.attempt.key).state == 'awaiting_review')
            with worker.lock: pass
            for _ in range(2): self.assertTrue(self.service.reconcile(self.attempt.key))
        self.assertEqual(self.applies, [True])
        self.assertEqual((self.source / 'fixture').read_text(), 'changed by fixture\n')
        self.assertEqual(len(json.loads((self.root / 'ledger.json').read_text())), 1)
        go = [json.loads(x) for x in (self.root / 'go.jsonl').read_text().splitlines()]
        self.assertEqual(len(go), 1); self.assertEqual(go[0]['cost_usd'], .01)
        r = self.store.get(self.attempt.key)
        self.assertIsNone(r.reservation)
        self.assertEqual(len(r.settle_keys), 5)
        self.assertEqual(json.loads(Path(r.artifacts['report']['metadata']).read_text())['quota']['used_percent'], 5)
        reconstructed = reconstruct_context(r.receipt['completion']['context'])
        self.assertEqual(reconstructed, self.ctx)
        self.assertEqual(conflicts, [True])
        self.assertEqual(json.loads(Path(r.artifacts['report']['registry']).read_text())['label'], 'fixture-label')
        # A second execution exercises Codex account/window projection without
        # reading any real account path or invoking a backend CLI.
        options = dict(self.inv.fixed_options)
        options['options'] = {'home': str(self.root / 'fixture-codex-account')}
        self.inv = dataclasses.replace(self.inv, invocation_id='codex-fixture', backend='codex', account_alias='gpt', model='gpt-6.1-sol', effort='low', fixed_options=options)
        self.attempt = Attempt('codex-fixture', 'try', 1, 'codex-request')
        self.admission.admit(self.inv, self.attempt, max_parallel=1)
        self.service.bind(self.attempt.key, self.ctx, ledger_path=self.root / 'ledger.json', registry_dir=self.root / 'registry',
                          policy='no_apply', codex_ledger=self.root / 'codex.jsonl')
        worker.runner = self.runner(); worker.default_runner = False
        worker.start(self.inv, self.attempt, 'codex fixture')
        self.wait(lambda: self.store.get(self.attempt.key).state == 'awaiting_review')
        with worker.lock: pass
        codex = [json.loads(x) for x in (self.root / 'codex.jsonl').read_text().splitlines()]
        self.assertEqual(len(codex), 1)
        self.assertEqual(codex[0]['codex_home'], 'fixture-codex-account')

    def test_crash_sink_reconciliation_deduplicates_and_ambiguous_apply_holds(self):
        self.applies = []
        worker = ExecutionWorker(self.store, self.supervisor, runner=self.runner())
        self.service.attach(worker)
        actual = self.service._ledger
        def crash(*args):
            actual(*args)
            raise RuntimeError('lost sink ACK')
        with patch.object(isolation, 'finalize', self.finalize), patch.object(self.service, '_ledger', crash):
            worker.start(self.inv, self.attempt, 'fixture')
            self.wait(lambda: self.store.get(self.attempt.key).settle_keys.get('ledger', {}).get('state') == 'in_progress')
            with worker.lock: pass
        self.assertIsNotNone(self.store.get(self.attempt.key).reservation)
        recovered = CompletionService(self.store, self.supervisor, self.admission).attach(worker)
        self.assertTrue(recovered.reconcile(self.attempt.key))
        self.assertEqual(len(json.loads((self.root / 'ledger.json').read_text())), 1)
        self.assertEqual(self.applies, [True])
        # An old summary predating the durable Go row proves nothing.
        r = self.store.get(self.attempt.key)
        saved_summary = (self.root / 'go-summary.json').read_text()
        r.state = 'settling'; r.reservation = {'fixture': True}
        r.settle_keys['go_ledger']['state'] = 'in_progress'
        self.store.compare_and_swap(r.key, r.revision, r)
        (self.root / 'go-summary.json').write_text(json.dumps({'updated_at': int(r.finished_at), 'models': {}}))
        self.assertFalse(recovered.reconcile(r.key))
        self.assertIsNotNone(self.store.get(r.key).reservation)
        (self.root / 'go-summary.json').write_text(saved_summary)
        # Missing apply proof cannot be repaired by rerunning finalize.
        r = self.store.get(self.attempt.key)
        r.state = 'settling'; r.reservation = {'fixture': True}
        r.settle_keys['finalize']['state'] = 'in_progress'
        recovered._proof(r, 'finalize').unlink()
        self.store.compare_and_swap(r.key, r.revision, r)
        with patch.object(isolation, 'finalize', side_effect=AssertionError('unsafe replay')):
            self.assertFalse(recovered.reconcile(r.key))
        self.assertIsNotNone(self.store.get(r.key).reservation)

    def test_nonquiescent_and_failure_never_apply(self):
        self.confirmed = False; self.applies = []
        worker = ExecutionWorker(self.store, self.supervisor, runner=self.runner(Status.FAILED))
        self.service.attach(worker)
        with patch.object(isolation, 'finalize', self.finalize):
            worker.start(self.inv, self.attempt, 'fixture')
            self.wait(lambda: self.store.get(self.attempt.key).pending_outcome is not None)
            with worker.lock: pass
            self.assertFalse(self.service.reconcile(self.attempt.key))
            self.assertEqual(self.applies, [])
            self.assertIsNotNone(self.store.get(self.attempt.key).reservation)
            self.confirmed = True
            self.assertTrue(self.service.reconcile(self.attempt.key))
        self.assertEqual(self.applies, [False])
        observation = self.store.get(self.attempt.key).receipt['usage_observation']
        self.assertTrue(observation['capacity_failure'])
        self.assertNotIn('errors', observation)
        self.assertTrue(self.iso.is_dir())


if __name__ == '__main__': unittest.main()
