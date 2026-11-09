"""Package B: temporary configuration and mocked Paseo only."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from side_session import actions, commands, paseo, state
from side_session.cli import build_parser
from side_session.config import load_config

class ConfigBTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, HOME=str(self.root), HYBRID_HANDS_CONFIG=str(self.root/'global.json')))
        self.stack.enter_context(patch('side_session.config.git_toplevel', return_value=self.root))
        (self.root/'global.json').write_text(json.dumps({'main_session': {'codex_model': 'main-model', 'codex_effort': 'medium'}, 'side_session': {'codex_model': 'side-model'}}))
        self.cfg = load_config(self.root)
    def run_start(self, *flags):
        args = build_parser().parse_args(['start', '--name', 'fixture', *flags])
        with redirect_stdout(io.StringIO()) as out:
            result = actions.start(self.cfg, args)
        return result, out.getvalue()
    def test_main_config_and_cli(self):
        with patch.object(paseo, '_call', side_effect=AssertionError('dry run daemon call')):
            for flags, model, effort in (([], 'main-model', 'medium'), (['--model', 'override', '--effort', 'high'], 'override', 'high')):
                result, out = self.run_start('--main', '--dry-run', *flags)
                self.assertEqual(result, 0); self.assertIn(f'model={model} effort={effort}', out)
                self.assertNotIn('side-model', out)
        self.assertFalse(self.cfg.state_dir.exists())
    def test_claude_paseo_plan_payload_failure(self):
        config = json.loads((self.root/'global.json').read_text())
        for section in ('side_session', 'main_session'):
            config[section].update(provider='claude', claude_account='v2', claude_model='configured-model', claude_effort='medium')
        config['side_session']['budget_check_cmd'] = ['fixture-guard']
        (self.root/'global.json').write_text(json.dumps(config))
        self.cfg = load_config(self.root)
        with patch.object(paseo, '_call', side_effect=AssertionError('dry run daemon call')), patch.object(actions, '_uses_day_guard', return_value=False) as guard:
            for main in ([], ['--main']):
                for override, account, model, effort in (([], 'v2', 'configured-model', 'medium'), (['--provider', 'claude', '--account', 'v1', '--model', 'cli-model', '--effort', 'high'], 'v1', 'cli-model', 'high')):
                    result, out = self.run_start(*main, '--prompt', 'fixture', '--dry-run', *override)
                    self.assertEqual(result, 0); guard.assert_called_with(self.cfg, 'claude', account)
                    self.assertIn(f'model={model} effort={effort}', out)
                    self.assertIn(str(self.root/('.claude-hand' if account == 'v2' else '.claude')), out)
        (self.root/'global.json').write_text('{}'); self.cfg = load_config(self.root)
        with patch.object(paseo, '_call', side_effect=AssertionError('dry run daemon call')):
            result, out = self.run_start('--provider', 'claude', '--account', 'v2', '--prompt', 'fixture', '--dry-run')
        self.assertEqual(result, 0); self.assertIn('"provider": "claude"', out)
        self.assertIn('"modeId": "bypassPermissions"', out); self.assertIn('"no-chrome": null', out)
        self.assertIn(str(self.root/'.claude-hand'), out); self.assertIn('claude-opus-5-5', out)
        with patch.object(paseo, '_call', return_value={}) as call:
            paseo.start_agent(workdir=str(self.root), name='fixture', model='claude-opus-5-5', effort='high', initial_prompt='fixture', codex_home=self.cfg.codex_home, target_key='fixture', hand_scope='scope', project_root=str(self.root), provider='claude', claude_config_dir=str(self.root/'.claude-hand'))
        payload = call.call_args.args[1]
        self.assertEqual(payload['env'], {'CLAUDE_CONFIG_DIR': str(self.root/'.claude-hand'), 'HYBRID_HANDS_HAND_SCOPE': 'scope'})
        self.assertEqual((payload['provider'], payload['model'], payload['effort']), ('claude', 'claude-opus-5-5', 'high'))
        with patch.object(paseo, 'cli_package_root', return_value=self.root), patch.object(paseo, 'disabled', return_value=False), patch.object(paseo, 'ready', return_value={'targetKey': 'fixture'}), patch.object(paseo, 'start_agent', side_effect=paseo.PaseoError('AGENT_CREATE_FAILED')), patch.object(paseo.codex_trust, 'ensure_codex_compact_limit') as compact, patch.object(actions.subprocess, 'run') as screen:
            result, out = self.run_start('--provider', 'claude', '--account', 'v2', '--prompt', 'fixture')
        self.assertEqual(result, 1); self.assertIn('không fallback screen', out)
        compact.assert_not_called(); screen.assert_not_called()
        st = state.load(self.cfg.state_dir, 'fixture')
        self.assertEqual((st.account, st.transport, st.model, st.effort), ('v2', 'paseo', 'claude-opus-5-5', 'high'))
        paseo.capture_native_id(st, 'native-fixture')
        self.assertEqual((st.native_session_id, st.codex_thread_id), ('native-fixture', ''))
    def test_main_template_absolute_tools_and_brief(self):
        rendered = commands.build_main_codex_prompt('fixture', 'actual-model', 'medium')
        root = commands.SIDE_BIN.parent.parent
        for path in ('bin/hand-ext', 'bin/side-session', 'bin/hh-ps', 'skills/ext-hand/SKILL.md', 'skills/side-session/SKILL.md'):
            self.assertIn(str(root/path), rendered)
        self.assertIn((root/'templates/hand-brief.md').read_text(), rendered)
        self.assertIn('Codex actual-model medium', rendered)

    def test_main_claude_compact_launch_and_display(self):
        from dataclasses import replace
        from side_session.constants import CLAUDE_AUTO_COMPACT_ENV as key
        for value in (272000, 400000, None, 'auto'):
            self.cfg = replace(self.cfg, main_session={} if value == 272000 else {'claude_auto_compact_window': value})
            for transport in ('screen', 'paseo'):
                self.cfg = replace(self.cfg, transport=transport, main_session={**self.cfg.main_session, "transport": transport})
                for account in ('v1', 'v2'):
                    for main in (False, True):
                        applied = value if main and isinstance(value, int) else None
                        with patch.dict(os.environ, {key: '272000'}), patch.object(paseo, '_call', side_effect=AssertionError('no daemon')):
                            result, out = self.run_start('--provider', 'claude', '--account', account, '--prompt', 'fixture', '--dry-run', *(['--main'] if main else []))
                            self.assertNotIn(key, paseo.clean_env())
                        self.assertEqual(result, 0)
                        self.assertIn(f'{key}={applied}' if transport == 'screen' else f'"{key}": "{applied}"', out) if applied else self.assertNotIn(f'{key}=' if transport == 'screen' else f'"{key}":', out)
        for role, window in (('main', 272000), ('main', None), ('', None)):
            st = state.SessionState('fixture', 'u', 'claude', str(self.root), '', '', 300000, 0, 'running', '', role=role, claude_auto_compact_window=window)
            self.assertEqual(actions._token_cell(self.cfg, st, 400000), '400000/272000 (tự nén)' if window else '400000/300000 !')
        with patch.object(paseo, '_call', return_value={}) as call:
            paseo.start_agent(workdir=str(self.root), name='fixture', model='claude-opus-5-5', effort='high', initial_prompt='fixture', codex_home=self.cfg.codex_home, target_key='fixture', hand_scope='scope', project_root=str(self.root), provider='claude', claude_auto_compact_window=272000)
        self.assertEqual(call.call_args.args[1]['env'][key], '272000')
