"""Operational CLI tests, using only synthetic local metadata and fake transport."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import cli
from hand_ext.paseo_controller import PaseoController
from hand_ext.paseo_gateway import Gateway
from hand_ext.paseo_transport import PaseoTransport
import test_hand_paseo_controller as fixtures

class ManagedCliTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ControllerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def command(self, action, key=None, brief=None):
        argv = ['managed', action, '--cwd', str(self.f.repo)]
        if key is not None:
            argv += ['--key', f'{key.invocation_id}:{key.attempt_id}:{key.epoch}']
        if brief is not None:
            argv += ['--brief', str(brief)]
        out = io.StringIO()
        with patch.object(cli, '_cfg', return_value=self.f.cfg), patch('sys.stdout', out):
            code = cli.main(argv)
        return code, json.loads(out.getvalue())

    def transport(self):
        inv, attempt, sup, admission, completion = self.f.intent()
        worker = fixtures.FinishingWorker(self.f.store, sup, completion)
        gateway = Gateway(self.f.store, admission, worker, invocation_id=inv.invocation_id,
                          wait_seconds=1, completion=completion)
        calls = []
        def client(request):
            calls.append(request)
            result = dict(ok=True, targetKey=transport.target_key)
            if request['command'] in ('archive', 'reopen'):
                result['state'] = {'archive': 'archived', 'reopen': 'reopened'}[request['command']]
            if request['command'] == 'probe':
                result['providers'] = ['hh-hand-codex']
            if request['command'] == 'parent':
                result.update(parentAgentId='parent-agent', projectId='project')
            if request['command'] == 'send':
                gateway.handle('session/prompt', dict(sessionId=inv.invocation_id,
                    messageId=request['messageId'], prompt=[dict(type='text', text=request['brief'])]))
            return result
        package = Path(__file__).parent / 'fixtures/hand_paseo/transport/package'
        transport = PaseoTransport(package.resolve(), {'kind':'instance', 'home':str(self.f.root/'daemon')},
                                    client_factory=lambda *a: client, store=self.f.store)
        controller = PaseoController(self.f.cfg, self.f.store, transport, supervisor=sup,
                                     admission=admission, completion=completion)
        controller.dispatch(inv, attempt, 'synthetic first brief', transport.verify_parent('parent-agent'))
        return attempt, transport, calls

    def test_ls_local_metadata_and_parser_errors(self):
        inv, attempt, *_ = self.f.intent()
        with patch('hand_ext.paseo_controller.transport_from_config', side_effect=AssertionError('no daemon')):
            code, result = self.command('ls')
        self.assertEqual(code, 0)
        self.assertEqual(result['executions'][0]['key'], f'{inv.invocation_id}:{attempt.attempt_id}:1')
        self.assertNotIn('receipt', result['executions'][0])
        self.assertNotIn('fixed_options', result['executions'][0])
        for key in ('missing', 'a:b:0', 'a:b:-1', 'a:b:1:extra'):
            with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit) as error:
                cli._parser().parse_args(['managed','archive','--cwd',str(self.f.repo),'--key',key])
            self.assertEqual(error.exception.code, 2)
        with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
            cli._parser().parse_args(['managed','followup','--cwd',str(self.f.repo),'--key','a:b:1'])

    def test_review_archive_followup_exact_epoch_and_history(self):
        attempt, transport, calls = self.transport()
        archived = self.f.store.get(attempt.key)
        self.assertEqual(archived.state, 'archived')
        self.assertNotIn('review', archived.artifacts)
        brief = self.f.root/'fresh.md'; brief.write_text('fresh self-contained synthetic brief')
        with patch('hand_ext.paseo_controller.transport_from_config', return_value=transport):
            self.assertEqual(self.command('review-approve', attempt.key)[0], 0)
            self.assertEqual(self.command('archive', attempt.key)[0], 0)
            first = self.f.store.get(attempt.key).to_dict()
            code, result = self.command('followup', attempt.key, brief)
        self.assertEqual(code, 0)
        key = cli._execution_key(result['execution']['key'])
        self.assertEqual(key.epoch, 2)
        second = self.f.store.get(key)
        preserved = self.f.store.get(attempt.key).to_dict()
        for field in ('artifacts', 'outcome', 'settle_keys', 'attempt'):
            self.assertEqual(preserved[field], first[field])
        self.assertEqual(preserved['receipt']['completion'], first['receipt']['completion'])
        self.assertEqual(second.attempt.agent_id, first['attempt']['agent_id'])
        self.assertEqual(second.attempt.workspace_id, first['attempt']['workspace_id'])
        self.assertEqual(second.state, 'archived')
        self.assertNotEqual(second.attempt.request_key, attempt.request_key)
        self.assertNotEqual(second.receipt['completion']['context']['baseline_tree'],
                            first['receipt']['completion']['context']['baseline_tree'])
        patch_text = Path(second.artifacts['finalize']['result']['patch_path']).read_text()
        self.assertIn('+epoch2', patch_text); self.assertNotIn('+epoch1', patch_text)
        self.assertEqual(sum(c['command']=='create' for c in calls), 1)
        self.assertEqual(sum(c['command']=='archive' for c in calls), 3)

    def test_recover_flags_and_safe_diagnostics(self):
        from hand_ext.execution_state import StateConflict
        from hand_ext.execution_admission import AdmissionConflict, admission_diagnostic
        from hand_ext.legacy_attestation import LegacyOwnerAlive
        _, attempt, *_ = self.f.intent()
        key = attempt.key
        argv = ['managed', 'recover', '--cwd', str(self.f.repo), '--key',
                f'{key.invocation_id}:{key.attempt_id}:{key.epoch}',
                '--legacy-attest', '--reason', 'operator checked', '--apply',
                '--owner-os-start', '90']
        for error in (StateConflict('SECRET_ENV_ARGV'), LegacyOwnerAlive('SECRET_ENV_ARGV')):
            out = io.StringIO()
            with patch.object(cli, '_cfg', return_value=self.f.cfg), patch('sys.stdout', out), patch('hand_ext.paseo_recovery.recover', side_effect=error) as call:
                self.assertEqual(cli.main(argv), 1)
            self.assertNotIn('SECRET_ENV_ARGV', out.getvalue())
            self.assertTrue(call.call_args.kwargs['legacy_attest'])
            self.assertEqual(call.call_args.kwargs['owner_os_start'], '90')
        self.assertIn('public Paseo', out.getvalue())
        safe = admission_diagnostic(AdmissionConflict('SECRET_ENV_ARGV'))
        self.assertNotIn('SECRET_ENV_ARGV', json.dumps(safe))
        self.assertEqual(admission_diagnostic(AdmissionConflict('claims_conflict', key))['holding_key']['epoch'], 1)
        from hand_ext.execution_state import ExecutionKey
        for bad in (ExecutionKey('bad/path', 'a', 1), ExecutionKey('a'*129, 'b', 1), ExecutionKey('a', 'b', True)):
            self.assertIsNone(admission_diagnostic(AdmissionConflict('claims_conflict', bad))['holding_key'])
        from hand_ext.execution_admission import AdmissionFull
        for error in (AdmissionConflict('claims_conflict', key), AdmissionFull('pool_full', key)):
            brief = self.f.root/'admission.md'; brief.write_text('synthetic brief')
            out = io.StringIO()
            with patch.object(cli, '_cfg', return_value=self.f.cfg), patch('sys.stderr', out), patch('hand_ext.paseo_controller.transport_from_config'), patch.object(PaseoController, 'preflight', return_value={}), patch.object(PaseoController, 'dispatch', side_effect=error):
                self.assertEqual(cli.main(['run', '--cwd', str(self.f.repo), '--brief', str(brief), '--mode', 'paseo-required']), 8)
            self.assertIn(error.kind, out.getvalue())

    def test_guards_unknown_unreviewed_unquiescent_and_stale(self):
        attempt, transport, calls = self.transport()
        brief = self.f.root/'fresh.md'; brief.write_text('new synthetic brief')
        with patch('hand_ext.paseo_controller.transport_from_config', return_value=transport):
            self.assertEqual(self.command('archive', attempt.key)[0], 0)
            self.assertEqual(self.f.store.get(attempt.key).state, 'archived')
            self.assertEqual(self.command('followup', attempt.key, brief)[0], 1)
            record = self.f.store.get(attempt.key)
            record.quiescence = None
            self.f.store.compare_and_swap(record.key, record.revision, record)
            self.assertEqual(self.command('review-approve', attempt.key)[0], 1)
            record = self.f.store.get(attempt.key)
            record.quiescence = dict(confirmed=True, evidence='fixture reaped')
            self.f.store.compare_and_swap(record.key, record.revision, record)
            self.assertEqual(self.command('review-approve', attempt.key)[0], 0)
            self.assertEqual(self.command('followup', attempt.key, brief)[0], 0)
            before = len(calls)
            for action in ('review-approve','archive','followup'):
                self.assertEqual(self.command(action, attempt.key, brief if action=='followup' else None)[0], 1)
            self.assertEqual(len(calls), before)
            unknown = cli._execution_key('unknown:unknown:1')
            self.assertEqual(self.command('archive', unknown)[0], 1)
            self.assertEqual(len(calls), before)

if __name__ == '__main__':
    unittest.main()


def setUpModule():  # keep hh-store revision bumps out of the real ~/.hybrid-hands
    import os as _os, tempfile as _tempfile
    from unittest import mock as _mock
    global _STATE_TMP, _STATE_ENV
    _STATE_TMP = _tempfile.TemporaryDirectory()
    _STATE_ENV = _mock.patch.dict(_os.environ, {"HYBRID_HANDS_STATE_DIR": _STATE_TMP.name})
    _STATE_ENV.start()


def tearDownModule():
    _STATE_ENV.stop()
    _STATE_TMP.cleanup()
