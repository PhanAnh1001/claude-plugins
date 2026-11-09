"""Offline managed lifecycle across the real worker, settlement, projection and CLI."""
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
import test_hand_paseo_controller as fixtures
from hand_ext import cli
from hand_ext.backends.base import RunState, Status, Usage
from hand_ext.execution_state import _plain
from hand_ext.execution_supervisor import ProcessIdentity
from hand_ext.execution_worker import ExecutionWorker
from hand_ext.paseo_controller import PaseoController, terminal_evidence
from hand_ext.paseo_gateway import Gateway
from hand_ext.paseo_transport import PaseoTransport
from hand_ext.runner import RunOutcome
from hh_ps import tree
from hh_ps.models import Session
from hh_ps.render import render_json


class ManagedIntegrationTests(unittest.TestCase):
    def test_dispatch_worker_completion_snapshot_review_archive_followup(self):
        # Install the fake home before loading config or constructing any fixture.
        home_temp = tempfile.TemporaryDirectory()
        self.addCleanup(home_temp.cleanup)
        home = Path(home_temp.name)
        env = patch.dict(os.environ, {'PATH': os.environ.get('PATH', ''), 'HOME': str(home),
            'CLAUDE_HOME': str(home/'.claude'), 'CLAUDE_CONFIG_DIR': str(home/'.claude'),
            'CODEX_HOME': str(home/'.codex-hand'), 'GIT_CONFIG_NOSYSTEM': '1'}, clear=True)
        env.start(); self.addCleanup(env.stop)
        f = fixtures.ControllerTests()
        f.setUp(); self.addCleanup(f.doCleanups)
        inv, attempt, supervisor, admission, completion = f.intent()
        # Bind real apply and all usage sinks, entirely inside disposable paths.
        f.cfg = replace(f.cfg, runs_dir=f.root/'worker')
        record = f.store.get(attempt.key)
        binding = record.receipt['completion']
        binding.update(policy='apply', registry=str(f.cfg.machine_state_dir/'runs'),
                       codex_ledger=str(f.cfg.machine_state_dir/'codex-usage.jsonl'),
                       quota_path=str(f.cfg.quota_state))
        f.store.compare_and_swap(record.key, record.revision, record)
        launches, threads, calls = [], [], []

        def runner(backend, spec, *, control):
            threads.append(threading.current_thread())
            launches.append(control.key)
            supervisor.register_writer(control.key,
                ProcessIdentity(100 + control.key.epoch, 100 + control.key.epoch,
                                'synthetic-epoch-' + str(control.key.epoch)), control.owner)
            target = spec.cwd/'file.txt'
            target.write_text(target.read_text() + f'epoch{control.key.epoch}\n')
            return RunOutcome(Status.OK, 0,
                RunState(Usage(input=100 * control.key.epoch, cached_input=20,
                               output=10 * control.key.epoch), final_text='synthetic result'), .01)

        worker = ExecutionWorker(f.store, supervisor, runner=runner)
        completion.attach(worker)
        def join_workers():
            for thread in threads:
                thread.join(2)
                self.assertFalse(thread.is_alive(), 'worker must exit within cleanup bound')
        self.addCleanup(join_workers)
        gateway = Gateway(f.store, admission, worker, invocation_id=inv.invocation_id,
                          completion=completion, wait_seconds=2)
        def client(request):
            calls.append(request)
            result = dict(ok=True, targetKey=transport.target_key)
            if request['command'] in ('archive', 'reopen'):
                result['state'] = {'archive': 'archived', 'reopen': 'reopened'}[request['command']]
            if request['command'] == 'probe': result['providers'] = ['hh-hand-codex']
            if request['command'] == 'parent':
                result.update(parentAgentId='parent-agent', projectId='project')
            if request['command'] == 'send':
                gateway.handle('session/prompt', dict(sessionId=inv.invocation_id,
                    messageId=request['messageId'],
                    prompt=[dict(type='text', text=request['brief'])]))
            return result
        package = Path(__file__).parent/'fixtures/hand_paseo/transport/package'
        transport = PaseoTransport(package.resolve(), {'kind':'instance', 'home':str(home/'daemon')},
                                    client_factory=lambda *a: client, store=f.store)
        controller = PaseoController(f.cfg, f.store, transport, supervisor=supervisor,
                                     admission=admission, completion=completion)
        first = controller.dispatch(inv, attempt, 'first self-contained synthetic brief',
                                    controller.preflight('codex', 'parent-agent'))
        join_workers()
        self.assertTrue(terminal_evidence(first))
        self.assertEqual(first.state, 'archived')
        self.assertNotIn('review', first.artifacts)
        self.assertEqual(first.outcome['provenance'], 'runner')
        self.assertIsNone(first.reservation)
        self.assertEqual(set(first.settle_keys), {'finalize','report','ledger','go_ledger','usage_state'})
        self.assertTrue(all(v['state']=='completed' for v in first.settle_keys.values()))
        self.assertEqual((f.repo/'file.txt').read_text(), 'baseline\nepoch1\n')

        # Synthetic rollout aliases must be suppressed by the production native mapper.
        native = home/'.codex-hand/sessions'; native.mkdir(parents=True)
        stamp = datetime.now(timezone.utc).isoformat()
        payload = dict(id='synthetic-runner-root', cwd=inv.isolated_cwd, timestamp=stamp)
        (native/'rollout-synthetic.jsonl').write_text(json.dumps(dict(type='session_meta', payload=payload))+'\n')
        def sessions(*args, **kwargs):
            return [Session(inv.parent_session, 'canonical parent', 'running', str(f.repo),
                            0, time.time()-60, time.time(), True, True)]
        def snapshot():
            # Only source discovery is injected: managed mapping, dedup, pricing,
            # account enrichment, native scanning and JSON rendering all run normally.
            with patch.object(tree, 'load_hand_ext_config', return_value=f.cfg), \
                 patch.object(tree, 'state_root', return_value=f.cfg.machine_state_dir), \
                 patch.object(tree, 'load_sessions', side_effect=sessions), \
                 patch('hh_ps.claude_calibration.enrich'):
                return tree.build_snapshot(f.repo, 3600, False, main_session_id=inv.parent_session)
        snap = snapshot()
        self.assertEqual([s.session_id for s in snap.sessions], [inv.parent_session])
        self.assertEqual(snap.orphan_runs, [])
        self.assertEqual(len(list(snap.iter_runs())), 1)
        row = render_json(snap)['sessions'][0]['hand_runs'][0]
        self.assertEqual(row['execution_key'], _plain(attempt.key))
        self.assertEqual(row['tokens'], first.outcome['usage'])
        self.assertEqual(snap.sessions[0].subagents, [])
        self.assertIsNotNone(snap.sessions[0].hand_runs[0].usage.usd)
        # Completion has multiple sinks; projection must still show parser totals once.
        self.assertEqual(len(json.loads(f.cfg.ledger.read_text())), 1)
        artifacts = {name: Path(first.artifacts['report'][name]).read_bytes()
                     for name in ('report', 'metadata', 'registry')}
        patch1 = Path(first.artifacts['finalize']['result']['patch_path']).read_bytes()
        first_usage = dict(first.outcome['usage'])
        first_baseline = first.receipt['completion']['context']['baseline_tree']
        brief = f.root/'followup.md'; brief.write_text('fresh self-contained synthetic second brief')
        def command(action, key, brief_file=None):
            args = ['managed', action, '--cwd', str(f.repo), '--key',
                    f'{key.invocation_id}:{key.attempt_id}:{key.epoch}']
            if brief_file: args += ['--brief', str(brief_file)]
            out = io.StringIO()
            with patch.object(cli, '_cfg', return_value=f.cfg), \
                 patch('hand_ext.paseo_controller.transport_from_config', return_value=transport), \
                 patch('sys.stdout', out):
                code = cli.main(args)
            self.assertEqual(code, 0, out.getvalue())
            return json.loads(out.getvalue())
        command('review-approve', attempt.key)
        command('archive', attempt.key)
        self.assertEqual(f.store.get(attempt.key).state, 'archived')
        result = command('followup', attempt.key, brief)
        join_workers()
        second = f.store.get(cli._execution_key(result['execution']['key']))
        self.assertEqual(second.key.epoch, 2)
        self.assertTrue(terminal_evidence(second))
        self.assertEqual(second.state, 'archived')
        self.assertEqual(second.attempt.agent_id, first.attempt.agent_id)
        self.assertEqual(second.attempt.workspace_id, first.attempt.workspace_id)
        self.assertNotEqual(second.attempt.request_key, first.attempt.request_key)
        self.assertNotEqual(second.receipt['completion']['context']['baseline_tree'], first_baseline)
        self.assertEqual((f.repo/'file.txt').read_text(), 'baseline\nepoch1\nepoch2\n')
        patch2 = Path(second.artifacts['finalize']['result']['patch_path']).read_text()
        self.assertIn('+epoch2', patch2); self.assertNotIn('+epoch1', patch2)
        self.assertEqual(Path(first.artifacts['finalize']['result']['patch_path']).read_bytes(), patch1)
        for name, content in artifacts.items():
            self.assertEqual(Path(first.artifacts['report'][name]).read_bytes(), content)
        self.assertEqual(f.store.get(attempt.key).outcome['usage'], first_usage)
        entries = json.loads(f.cfg.ledger.read_text())
        self.assertEqual(len(entries), 2)
        self.assertEqual({entry['execution_key']['epoch'] for entry in entries}, {1,2})
        final = snapshot()
        self.assertEqual(len(final.sessions), 1)
        rows = final.sessions[0].hand_runs
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(r.tokens['input'] for r in rows), 300)
        self.assertEqual({r.execution_key['epoch'] for r in rows}, {1,2})
        self.assertEqual(final.sessions[0].subagents, [])
        self.assertEqual(len(launches), 2)
        self.assertEqual(sum(r['command']=='create' for r in calls), 1)
        archive = [r for r in calls if r['command']=='archive']
        self.assertEqual(len(archive), 3)
        self.assertTrue(all(r['agentId'] == first.attempt.agent_id and
                            r['workspaceId'] == first.attempt.workspace_id for r in archive))

if __name__ == '__main__':
    unittest.main()
