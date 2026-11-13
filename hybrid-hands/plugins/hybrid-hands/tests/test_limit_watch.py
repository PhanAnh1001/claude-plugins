"""Three acceptance scenarios; all account, CLI and transport data is synthetic."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / 'lib'))
from hand_ext.limit_watch import adapters, engine, sources
from hand_ext.limit_watch.cli import target_registration, finish_target
from hand_ext.limit_watch.store import Store, empty

NOW = 1800000000


def window(key='five_hour', pct=100, reset=NOW+60, at=NOW-5):
    return dict(id=key, used_pct=pct, reset_at=reset, observed_at=at)


class LimitWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root / 'watch/state.json')
        self.target = dict(id='fake', provider='claude', account='v2', adapter='paseo',
                           account_home=str(self.root), cwd=str(self.root), native_id='native-fake',
                           agent_id='agent-fake', workspace_id='workspace-fake',
                           target_key='home:'+str(self.root), target=dict(kind='instance', home=str(self.root)),
                           paseo_provider='claude', work_pending=True, checkpoint='finished fake step',
                           next_step='next fake step', state='armed', armed_after=NOW-10,
                           work_observed_at=NOW-10, attempts=0)
        self.live = dict(valid=True, idle=True)
        self.sender = Mock(return_value='accepted')
        self.quota = Mock(return_value=dict(complete=True, windows=[window(pct=10, at=NOW)]))

    def test_add_self_dry_run(self):
        from hand_ext.limit_watch import cli
        import argparse
        import contextlib
        import io
        parser = argparse.ArgumentParser()
        cli.register(parser.add_subparsers())
        args = parser.parse_args(['limit-watch', 'add', '--self', '--checkpoint', 'test', '--dry-run'])
        cfg = SimpleNamespace(repo=self.root, claude_accounts={'v2': {'config_dir': str(self.root)}})
        output = io.StringIO()
        with patch.object(cli, 'Store', return_value=self.store), patch('side_session.config.load_config', return_value=cfg), patch.object(adapters, 'bridge', return_value=self.target.copy()), patch.dict(os.environ, PASEO_AGENT_ID='agent-fake', CLAUDE_CONFIG_DIR=str(self.root)), patch.object(Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(output):
            self.assertEqual(cli.command(args), 0, output.getvalue())
        raw = json.loads(output.getvalue())
        self.assertEqual((raw['workspace_id'], raw['native_id'], raw['adapter']), ('workspace-fake', 'native-fake', 'paseo'))
        self.assertFalse(self.store.path.parent.exists())

    def test_add_missing_metadata(self):
        from hand_ext.limit_watch import cli
        import contextlib
        import io
        args = SimpleNamespace(action='add', self_target=True, side=None, checkpoint='test', next_step=None, id=None, dry_run=True, persistent=False, target=[], cwd=str(self.root))
        output = io.StringIO()
        with patch.object(cli, 'Store', return_value=self.store), patch('side_session.config.load_config'), patch.dict(os.environ, PASEO_AGENT_ID='agent-fake'), patch.object(adapters, 'bridge', return_value={'agent_id': 'agent-fake'}), contextlib.redirect_stdout(output):
            self.assertNotEqual(cli.command(args), 0)
        self.assertIn('workspace_id, native_id', output.getvalue())
        self.assertFalse(self.store.path.parent.exists())

    def test_add_side_preserves_other_target(self):
        from hand_ext.limit_watch import cli
        import contextlib
        import io
        self.seed(persistent=True)
        before = self.store.read()
        st = SimpleNamespace(name='sol', uuid='uuid-fake', transport='paseo', role='side', paseo_send_pending=False, paseo_agent_id='agent-side', claude_config_dir=str(self.root), paseo_workspace_id='workspace-fake', native_session_id='native-fake', provider='claude', paseo_target='home:'+str(self.root))
        cfg = SimpleNamespace(repo=self.root, state_dir=self.root, claude_accounts={'v2': {'config_dir': str(self.root)}})
        args = SimpleNamespace(action='add', self_target=False, side='sol', checkpoint='test', next_step=None, id=None, dry_run=False, persistent=False, target=[], cwd=str(self.root))
        metadata = dict(self.target, agent_id='agent-side')
        with patch.object(cli, 'Store', side_effect=lambda path=None: Store(path) if path else self.store), patch('side_session.config.load_config', return_value=cfg), patch('side_session.state.load', return_value=st), patch.object(adapters, 'side_record'), patch.object(adapters, 'bridge', return_value=metadata), patch.object(cli.launchd, 'install') as install, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.command(args), 0, output.getvalue())
        after = self.store.read()
        self.assertEqual((after['targets']['fake'], after['generation'], after['persistent']), (before['targets']['fake'], before['generation'], True))
        self.assertEqual(after['targets']['sol']['side_uuid'], 'uuid-fake')
        self.assertTrue((self.store.path.parent / 'targets/sol.json').exists())
        install.assert_not_called()

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, blocked=False, persistent=False):
        target = dict(self.target)
        if blocked:
            engine.record_block(target, NOW-5, [window()])
        data = empty()
        data.update(enabled=True, persistent=persistent, generation=7, targets={'fake': target})
        with self.store.locked():
            self.store.save(data)

    def tick(self, now=NOW, guard=lambda *_: True):
        engine.tick(self.store, lambda t: self.live, self.quota, self.sender, guard, now)

    def test_paseo_finished_turn_stays_armed(self):
        self.seed()
        self.live.update(done=True, status='idle')
        self.tick()
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'armed')
        self.sender.assert_not_called()

    def test_paseo_resume_rearms_until_new_block(self):
        self.seed(blocked=True)
        self.tick()
        self.live.update(blocked_at=NOW-5)
        self.tick(NOW+1)
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'armed')
        self.assertEqual(self.sender.call_count, 1)

    def test_done_rejects_pending_and_registration_rearms(self):
        self.seed()
        finish_target(self.store, 'fake')
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'done')
        self.assertEqual(target_registration(self.target.copy(), NOW)['state'], 'armed')
        self.seed(blocked=True)
        self.sender.return_value = 'unknown'
        self.tick()
        with self.assertRaises(ValueError):
            finish_target(self.store, 'fake')
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'dispatch_pending')

    def test_available_quota_is_silent(self):
        self.seed()
        self.tick()
        self.tick()
        self.sender.assert_not_called()
        self.quota.assert_not_called()  # account availability cannot create a blocked session
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'armed')
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        for live in (dict(valid=False), dict(valid=True, idle=False), dict(valid=True, closed=True)):
            with self.subTest(live=live):
                self.seed(blocked=True)
                self.live = live
                self.tick()
                self.sender.assert_not_called()
        # A second tick cannot acquire the same flock; off/registration uses this
        # same lock, so generation changes cannot race a reserved send.
        with self.store.locked():
            with self.assertRaises(BlockingIOError):
                self.tick()

    def test_blocked_fresh_resume_once_and_pending_is_sticky(self):
        self.target['adapter'] = 'side'
        self.seed(blocked=True)
        def accepted(target, prompt):
            reserved = self.store.read()['targets']['fake']
            self.assertEqual(reserved['state'], 'dispatch_pending')
            self.assertEqual(reserved['dispatch_generation'], 7)
            self.assertIn('làm tiếp', prompt)
            self.assertIn('next fake step', prompt)
            return 'accepted'
        self.sender.side_effect = accepted
        self.tick()
        self.tick()
        self.assertEqual(self.sender.call_count, 1)
        self.assertFalse(self.store.read()['enabled'])
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'resumed')
        self.seed(blocked=True, persistent=True)
        self.sender.reset_mock()
        self.tick()
        self.live['blocked_at'] = NOW-5  # old event is not a fresh block
        self.tick(NOW+1)
        self.assertEqual(self.sender.call_count, 1)
        self.assertEqual(self.store.read()['targets']['fake']['state'], 'armed')
        self.assertTrue(self.store.read()['enabled'])
        for outcome in ('unknown', RuntimeError('synthetic crash after dispatch')):
            with self.subTest(outcome=type(outcome).__name__):
                self.seed(blocked=True)
                self.sender.reset_mock()
                self.sender.side_effect = outcome if isinstance(outcome, Exception) else None
                self.sender.return_value = outcome
                self.live = dict(valid=True, idle=True)
                self.tick()
                self.live = dict(valid=True, idle=False, status='running')
                self.tick(NOW+1)
                self.assertEqual(self.sender.call_count, 1)
                self.assertEqual(self.store.read()['targets']['fake']['state'], 'dispatch_pending')
        # Exercise actual stdio handshake/parser with a fake executable, no account.
        script = self.root / 'fake-codex'
        script.write_text('#!'+sys.executable+'\n'+'''
import json, sys
def read(): return json.loads(sys.stdin.readline())
assert read()['method'] == 'initialize'
print(json.dumps({'id':1,'result':{}}), flush=True)
assert read()['method'] == 'initialized'
assert read()['method'] == 'account/rateLimits/read'
print(json.dumps({'id':2,'result':{'rateLimitsByLimitId':{'codex':{
 'primary':{'usedPercent':12,'windowDurationMins':300,'resetsAt':1800000600},
 'secondary':{'usedPercent':30,'windowDurationMins':10080,'resetsAt':1800600000}}}}}), flush=True)
''')
        script.chmod(0o700)
        sample = sources.codex_sample(sources.codex_rpc(str(self.root), str(self.root), str(script)), NOW)
        self.assertTrue(sample['complete'])
        self.assertEqual(len(sample['windows']), 2)
        self.assertFalse(sources.codex_sample({'rateLimits': {'primary': {}, 'rateLimitReachedType':'quota'}}, NOW)['complete'])
        # Real bridge code against an installed-client-shaped fixture. No daemon.
        if shutil.which('node'):
            client_dir = self.root / 'dist/utils'
            client_dir.mkdir(parents=True)
            (self.root / 'package.json').write_text('{"type":"module"}')
            agent = dict(id='agent-fake', workspaceId='workspace-fake', cwd=str(self.root),
                         provider='claude', persistence=dict(nativeHandle='native-fake'), status='idle',
                         pendingPermissions=[], activeTurn=None)
            for case, changes, expected in [('idle', {}, 'accepted'),
                    ('permissions', dict(pendingPermissions=[dict(id='fake')]), 'not_sent'),
                    ('running', dict(status='running'), 'not_sent'),
                    ('native changed', dict(persistence=dict(nativeHandle='different')), 'not_sent')]:
                with self.subTest(bridge=case):
                    fake_agent = {**agent, **changes}
                    (client_dir / 'client.js').write_text('export async function connectToDaemon(){return {'
                        'fetchAgent:async()=>({agent:'+json.dumps(fake_agent)+'}),'
                        'sendMessage:async()=>({}),close:async()=>{}}}')
                    request = dict(self.target, command='send', text='fake continuation')
                    proc = subprocess.run(['node', str(PLUGIN/'lib/hand_ext/limit_watch/paseo_bridge.mjs'),
                                           str(self.root)], input=json.dumps(request), text=True,
                                          capture_output=True, timeout=5, check=True)
                    self.assertEqual(json.loads(proc.stdout)['receipt'], expected)
        # Side identity is pinned again under side-session's own lock.
        from side_session import actions, state as side_state
        fake = SimpleNamespace(uuid='changed', paseo_agent_id='agent-fake', paseo_workspace_id='workspace-fake',
            paseo_target=self.target['target_key'], dir=str(self.root), native_session_id='native-fake', provider='claude')
        cfg = SimpleNamespace(state_dir=self.root/'side')
        cfg.state_dir.mkdir()
        pinned = dict(self.target, side_uuid='old')
        with patch.object(side_state, 'load', return_value=fake), patch.object(actions, '_preflight') as preflight:
            result = actions.send(cfg, SimpleNamespace(name='fake', _limit_watch_identity=pinned))
            self.assertNotEqual(result, 0)
            preflight.assert_not_called()

    def test_stale_metadata_expected_reset_has_one_attempt(self):
        self.seed(blocked=True)
        data = self.store.read()
        data['targets']['fake']['blocking_windows']['seven_day'] = window('seven_day', reset=NOW+300)
        with self.store.locked():
            self.store.save(data)
        self.quota.return_value = dict(complete=False, windows=[])  # offline/stale sources
        self.tick(NOW+181)  # first reset has passed, weekly reset has not
        self.sender.assert_not_called()
        self.tick(NOW+420, guard=lambda *_: False)  # internal guard remains binding
        self.sender.assert_not_called()
        self.sender.return_value = 'quota_rejected'
        self.tick(NOW+420)
        self.tick(NOW+90000)
        self.assertEqual(self.sender.call_count, 1)
        row = self.store.read()['targets']['fake']
        self.assertTrue(row['expected_reset_tried'])
        self.assertEqual(row['reason'], 'waiting_for_quota_observation')
        self.assertIn('reset dự kiến', self.sender.call_args.args[1])
        # A partial observation cannot clear the still-blocking weekly window.
        self.sender.reset_mock()
        self.quota.return_value = dict(complete=True, windows=[window(pct=0, at=NOW+10)])
        self.seed(blocked=True)
        data = self.store.read()
        data['targets']['fake']['blocking_windows']['seven_day'] = window('seven_day', reset=NOW+300)
        with self.store.locked(): self.store.save(data)
        self.tick(NOW+10)
        self.sender.assert_not_called()
        # Statusline mtime is fresh but inherited values are not observations.
        (self.root/'.statusline-cache.json').write_text(json.dumps(dict(five=0, week=0,
            five_reset=NOW+1000, week_reset=NOW+10000)))
        with patch.object(sources, 'cli_json', return_value={}), patch.dict(os.environ, {}, clear=False):
            sample = sources.claude_sample(self.target, NOW)
        self.assertTrue(all(w['observed_at'] is None for w in sample['windows']))
        # Registration requires explicit unfinished work; tmux is fail-closed.
        self.assertEqual(target_registration(dict(self.target, work_pending=False), NOW)['state'], 'done')
        with self.assertRaises(ValueError):
            target_registration(dict(self.target, adapter='tmux'), NOW)
        # Accepted by daemon then quota fails again: persistent must not consume
        # the same predicted reset repeatedly under fresh error timestamps.
        self.seed(blocked=True, persistent=True)
        self.quota.return_value = dict(complete=False, windows=[window()])
        self.sender.reset_mock()
        self.sender.return_value = 'accepted'
        self.tick(NOW+181)
        self.live = dict(valid=True, idle=True, blocked_at=NOW+182)
        self.tick(NOW+200)
        self.tick(NOW+9000)
        self.assertEqual(self.sender.call_count, 1)


if __name__ == '__main__':
    unittest.main()
