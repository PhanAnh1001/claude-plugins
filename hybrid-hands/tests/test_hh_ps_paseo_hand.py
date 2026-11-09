"""Managed hh-ps projection using disposable metadata and parser fixtures only."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / 'plugins/hybrid-hands/lib'))
sys.path.insert(0, str(TESTS / 'fixtures/hh_ps'))
from fixture import HhFixture, MAIN_SESSION, NOW, iso
from hand_ext.execution_state import Invocation, Attempt, ExecutionRecord, _plain
from hh_ps.paseo_source import execution_id
from hh_ps.registry_source import load_hand_runs
from hh_ps.tree import build_snapshot
from hh_ps.render import render_json
from hh_ps.compact import _run_mark


class PaseoHandTest(unittest.TestCase):
    def fixture(self):
        fx = HhFixture()
        self.addCleanup(fx.close)
        return fx

    def record(self, fx, *, epoch=1, run_id='managed', backend='codex', model='gpt-6.1-sol'):
        invocation = Invocation('inv', 'scope', MAIN_SESSION, 'paseo-parent',
            backend=backend, model=model, effort='low', source_cwd=str(fx.project),
            isolated_cwd=str(fx.project / 'isolated'))
        attempt = Attempt('inv', 'attempt', epoch, 'request-' + str(epoch), run_id,
            'target', 'project', 'workspace', 'agent')
        record = ExecutionRecord(invocation, attempt, state='awaiting_review',
            started_at=NOW - 60, finished_at=NOW - 10,
            outcome={'status': 'ok', 'backend_exit_code': 0,
                     'usage': {'input': 100, 'cached_input': 20, 'output': 10}},
            receipt={'worker_run_dir': str(fx.base / ('worker-' + str(epoch))),
                     'completion': {'registry': str(fx.runs), 'label': 'side-session:wrong'}})
        return record

    def save(self, fx, record, root=None):
        root = root or fx.state / 'executions'
        root.mkdir(parents=True, exist_ok=True)
        (root / (execution_id(_plain(record.key)) + '.json')).write_text(json.dumps(record.to_dict()))

    def snapshot(self, fx):
        with fx.env(), mock.patch('hh_ps.claude_calibration.enrich'):
            return build_snapshot(fx.project, 3600, False, now=NOW)

    def test_one_row_parent_dedup_parser_tokens_and_native_roots(self):
        fx = self.fixture()
        record = self.record(fx)
        record.artifacts = {'finalize': {'result': {'patch_path': str(fx.base / 'kept.patch')}},
            'report': {'report': str(fx.base / 'report.md'),
                       'metadata': str(fx.base / 'metadata.json'),
                       'registry': str(fx.runs / 'managed.json')}}
        metadata = dict(run_id='managed', execution_key=_plain(record.key),
            backend='wrong', model='wrong', parent_session='wrong', status='running',
            tokens={'input': 900, 'output': 900}, label='side-session:wrong')
        (fx.base / 'metadata.json').write_text(json.dumps(metadata))
        (fx.runs / 'managed.json').write_text(json.dumps(metadata))
        worker = Path(record.receipt['worker_run_dir'])
        worker.mkdir()
        (worker / 'meta.json').write_text(json.dumps(metadata))
        self.save(fx, record)
        native = fx.home / '.codex-hand/sessions'
        native.mkdir(parents=True)
        # The runner root has neither attempt.thread_id nor native parent linkage.
        for sid, cwd, parent in [('runner-root', record.invocation.isolated_cwd, None),
                                 ('runner-child', record.invocation.isolated_cwd, MAIN_SESSION),
                                 ('legacy-child', str(fx.project), MAIN_SESSION)]:
            payload = {'id': sid, 'cwd': cwd, 'timestamp': iso(NOW - 50)}
            if parent:
                payload['parent_thread_id'] = parent
            rows = [{'type': 'session_meta', 'payload': payload},
                    {'timestamp': iso(NOW - 10), 'type': 'event_msg',
                     'payload': {'type': 'task_complete'}}]
            (native / ('rollout-' + sid + '.jsonl')).write_text('\n'.join(map(json.dumps, rows)))
        snapshot = self.snapshot(fx)
        runs = [r for r in snapshot.iter_runs() if r.execution_key]
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual((run.parent_session, run.model, run.effort, run.status, run.exit_code),
                         (MAIN_SESSION, 'gpt-6.1-sol', 'low', 'ok', 0))
        self.assertEqual(run.tokens, {'input': 100, 'cached_input': 20, 'output': 10})
        self.assertIsNotNone(run.usage.usd)
        self.assertEqual(run.duration_seconds, 50)
        self.assertFalse(any(s.session_id == 'runner-root' for s in snapshot.sessions))
        native_ids = {a.agent_id for s in snapshot.sessions for a in s.subagents}
        self.assertNotIn('runner-child', native_ids)
        self.assertIn('legacy-child', native_ids)
        parent = next(s for s in render_json(snapshot)['sessions'] if s['session_id'] == MAIN_SESSION)
        row = next(r for r in parent['hand_runs'] if r['run_id'] == 'managed')
        self.assertEqual(row['execution_key']['epoch'], 1)
        self.assertEqual(row['patch_path'], str(fx.base / 'kept.patch'))
        self.assertEqual(row['duration_seconds'], 50)
        self.assertIn('main-run', {r.run_id for r in snapshot.iter_runs()})

    def test_followup_epochs_keep_old_row_and_distinct_fallback_id(self):
        fx = self.fixture()
        first = self.record(fx)
        second = self.record(fx, epoch=2, run_id=None)
        second.state, second.outcome, second.finished_at = 'running', None, None
        for record in (first, second):
            self.save(fx, record)
        second_id = execution_id(_plain(second.key))
        # Running parser registry has not yet acquired a completion execution_key.
        fx._run(second_id, run_dir=second.receipt['worker_run_dir'],
                tokens={'input': 30, 'cached_input': 0, 'output': 4})
        with fx.env():
            runs = [r for r in load_hand_runs(fx.state, NOW - 3600) if r.execution_key]
        self.assertEqual({r.run_id for r in runs}, {'managed', second_id})
        self.assertEqual({r.execution_key['epoch'] for r in runs}, {1, 2})
        self.assertEqual({r.agent_id for r in runs}, {'agent'})
        self.assertEqual({r.workspace_id for r in runs}, {'workspace'})
        active = next(r for r in runs if r.running)
        self.assertEqual(active.tokens['input'], 30)
        self.assertIsNone(active.ended_at)
        self.assertEqual(next(r for r in runs if not r.running).duration_seconds, 50)

    def test_unknown_error_precedence_and_legacy_unchanged(self):
        fx = self.fixture()
        record = self.record(fx)
        record.outcome, record.finished_at, record.state = None, None, 'unresolved'
        self.save(fx, record)
        # A stale sink cannot turn unresolved into success or manufacture an end.
        fx._run('managed', status='ok', ended_at=NOW, exit_code=0,
                run_dir=record.receipt['worker_run_dir'])
        with fx.env():
            runs = load_hand_runs(fx.state, NOW - 3600)
        run = next(r for r in runs if r.execution_key)
        self.assertEqual((run.status, run.exit_code, run.ended_at), ('unknown', None, None))
        self.assertEqual(run.state, 'unknown')
        self.assertEqual(_run_mark(run)[0], '?')
        unknown = next(r for r in self.snapshot(fx).iter_runs() if r.execution_key)
        self.assertIsNone(unknown.usage.usd)
        legacy = next(r for r in runs if r.run_id == 'main-run')
        self.assertTrue(legacy.running)
        self.assertIsNone(legacy.execution_key)
        record.outcome = {'status': 'ok', 'backend_exit_code': 9, 'usage': None}
        record.finished_at = NOW - 5
        self.save(fx, record)
        with fx.env():
            failed = next(r for r in load_hand_runs(fx.state, NOW - 3600) if r.execution_key)
        self.assertEqual((failed.status, failed.exit_code, _run_mark(failed)[0]), ('failed', 9, '✗'))
        self.assertEqual(failed.tokens, {})
        # Custom state roots are read without constructing/mutating ExecutionStore.
        custom = fx.base / 'custom-executions'
        self.save(fx, record, custom)
        custom_cfg = SimpleNamespace(paseo={'state_root': str(custom)},
            machine_state_dir=fx.base / 'unused-state', runs_dir=fx.base / 'unused-runs',
            ledger=fx.base / 'missing-ledger')
        # Empty primary root proves the configured state root is discovered.
        with fx.env():
            projected = load_hand_runs(fx.base / 'empty-state', NOW - 3600,
                                      [fx.project], known_configs={fx.project: custom_cfg})
        self.assertEqual(len([r for r in projected if r.execution_key]), 1)
        self.assertEqual(next(r for r in projected if r.execution_key).exit_code, 9)
        self.assertFalse((fx.base / 'empty-state').exists())
        for status in ('capped', 'quota_exhausted', 'not_logged_in', 'timeout', 'failed'):
            record.outcome = {'status': status, 'backend_exit_code': None, 'usage': None}
            self.save(fx, record)
            with fx.env():
                row = next(r for r in load_hand_runs(fx.state, NOW - 3600) if r.execution_key)
            self.assertEqual(row.status, status)
            self.assertEqual(_run_mark(row)[0], '✗')
        record.outcome = {'status': 'ok', 'backend_exit_code': 0,
                          'usage': {'input': 0, 'cached_input': 0, 'output': 0}}
        self.save(fx, record)
        zero = next(r for r in self.snapshot(fx).iter_runs() if r.execution_key)
        self.assertEqual(zero.usage.usd, 0)


if __name__ == '__main__':
    unittest.main()
