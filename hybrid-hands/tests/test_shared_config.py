"""Shared config precedence and offline inspection, using only temporary config."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'
sys.path.insert(0, str(LIB))
from shared_config import load_config, GlobalConfigError, normalize_claude_auto_compact_window
from hand_ext.cli import main
from hand_ext.config import load_config as load_hand
from hand_ext.run_cmd import _spec
from hh_ps.cli import main as ps_main
from side_session.cli import main as side_main


class SharedConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.global_file = self.root / 'global.json'
        env = patch.dict(os.environ, HOME=str(self.root), HYBRID_HANDS_CONFIG='global.json')
        env.start()
        self.addCleanup(env.stop)

    def test_precedence(self):
        self.global_file.write_text(json.dumps({'ext_hand': {'order': ['codex'], 'mode': 'auto',
            'paseo': {'package_root': 'package', 'state_root': 'state', 'target': {'host': 'fake'}}, 'backends': {
            'codex': {'effort': 'medium', 'home': 'codex', 'extra': {'a': 1, 'b': 2}, 'empty': {}},
            'claude': {'config_dir': 'claude'},
            'dsh': {'home': 'dsh', 'key_file': 'key', 'browser_dir': 'browser'}}}}))
        self.assertEqual(load_hand(self.root).options('codex')['effort'], 'medium')
        self.assertEqual(load_config(self.root).sources['ext_hand.backends.codex.empty'], 'global')
        repo = self.root / '.claude/hybrid-hands.json'
        repo.parent.mkdir()
        repo.write_text(json.dumps({'ext_hand': {'order': ['dsh'], 'mode': 'paseo-required',
            'paseo': {'state_root': 'repo-state'}, 'backends': {
            'codex': {'effort': 'high', 'extra': {}, 'empty': {'child': {}},
                      'price_per_mtok': None}}}}))
        from usage_pricing import explicit_options
        self.assertEqual(explicit_options(load_hand(self.root), 'codex'),
                         {'effort': 'high', 'home': 'codex', 'extra': {'a': 1, 'b': 2},
                          'empty': {'child': {}}, 'price_per_mtok': None})
        result = load_config(self.root)
        self.assertIsNone(result.effective['ext_hand']['backends']['codex']['price_per_mtok'])
        self.assertEqual(explicit_options(load_hand(self.root), 'dsh'),
                         {'home': 'dsh', 'key_file': 'key', 'browser_dir': 'browser'})
        self.assertEqual(result.effective['ext_hand']['order'], ['dsh'])
        self.assertEqual(result.effective['ext_hand']['backends']['codex']['extra'], {'a': 1, 'b': 2})
        self.assertEqual(result.sources['ext_hand.backends.codex.extra.b'], 'global')
        self.assertEqual(result.sources['ext_hand.backends.codex.effort'], 'repo')
        self.assertNotIn('ext_hand.backends.codex.empty', result.sources)
        self.assertEqual(result.sources['ext_hand.backends.codex.empty.child'], 'repo')
        cfg = load_hand(self.root)
        for name, key, relative in [('codex', 'home', 'codex'), ('claude', 'config_dir', 'claude'),
                                    ('claude-v2', 'config_dir', 'claude'), ('dsh', 'home', 'dsh'),
                                    ('dsh', 'key_file', 'key'), ('dsh', 'browser_dir', 'browser')]:
            self.assertEqual(cfg.options(name)[key], str(self.root / relative))
        self.assertEqual(cfg.options('codex')['effort'], 'high')
        self.assertEqual(cfg.mode, 'paseo-required')
        self.assertEqual(cfg.paseo, {'package_root': str(self.root / 'package'),
                                   'state_root': str(self.root / 'repo-state'), 'target': {'host': 'fake'}})
        self.assertEqual(result.sources['ext_hand.mode'], 'repo')
        self.assertEqual(result.sources['ext_hand.paseo.package_root'], 'global')
        self.assertEqual(result.sources['ext_hand.paseo.state_root'], 'repo')
        with patch('hand_ext.paseo_controller.cmd_managed_run', return_value=0) as managed:
            self.assertEqual(main(['run', '--brief', 'fake', '--cwd', str(self.root), '--mode', 'auto']), 0)
        self.assertEqual(managed.call_args.kwargs['mode'], 'auto')
        args = argparse.Namespace(model=None, effort='low', timeout_min=None, max_tokens=None, sandbox=None)
        spec = _spec(cfg, args, type('Backend', (), {'name': 'codex'})(), '', self.root, 'test')
        self.assertEqual(spec.effort, 'low')

    def test_missing_global(self):
        result = load_config(self.root)
        self.assertEqual(result.paths['global'], {'path': str(self.global_file), 'exists': False, 'read': False})
        from usage_pricing import explicit_options
        self.assertEqual(explicit_options(load_hand(self.root), 'codex'), {})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['config', '--json', '--cwd', str(self.root)]), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['effective']['ext_hand']['mode'], 'shell')
        self.assertEqual(payload['effective']['ext_hand']['paseo'], {})
        self.assertEqual(payload['sources']['ext_hand.mode'], 'plugin')
        self.assertEqual((payload['effective']['main_session']['claude_auto_compact_window'],
                          payload['sources']['main_session.claude_auto_compact_window']), (272000, 'plugin'))
        self.assertEqual(payload['sources']['ext_hand.paseo'], 'plugin')
        with patch.dict(os.environ):
            os.environ.pop('HYBRID_HANDS_CONFIG', None)
            self.assertEqual(load_config(self.root).paths['global'], {
                'path': str(self.root / '.hybrid-hands/config.json'), 'exists': False, 'read': False})

    def test_invalid_global(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        for raw in ('{', '[]', '{"ext_hand": []}', '{"ext_hand":{"backends":{"codex":[]}}}',
                    '{"side_session":[]}', '{"hh_ps":[]}', '{"ext_hand":{"go_usage":[]}}',
                    '{"ext_hand":{"backends":{"gemini":[]}}}', '{"ext_hand":{"claude_accounts":[]}}', '{"ext_hand":{"paseo":[]}}'):
            with self.subTest(raw=raw):
                self.global_file.write_text(raw)
                with self.assertRaisesRegex(GlobalConfigError, str(self.global_file)):
                    load_config(self.root)
                for cli, argv in ((main, ['config', '--json', '--cwd', str(self.root)]),
                                  (ps_main, ['--once', '--cwd', str(self.root)]),
                                  (side_main, ['ls']), (side_main, ['attach', 'fake'])):
                    with patch('pathlib.Path.cwd', return_value=self.root), contextlib.redirect_stderr(io.StringIO()) as errors:
                        self.assertNotEqual(cli(argv), 0)
                    self.assertIn(str(self.global_file), errors.getvalue())

    def test_main_claude_compact_config(self):
        repo, key = self.root / 'repo.json', 'claude_auto_compact_window'
        for value in (100000, 1000000, None, 'auto', 99999, 1000001, True, 272000.0, '272000', 'AUTO', [], {}):
            for source, path, error in (('global', self.global_file, GlobalConfigError), ('repo', repo, ValueError)):
                with self.subTest(value=value, source=source):
                    self.global_file.write_text(json.dumps({'main_session': {key: 300000}}))
                    repo.write_text('{}')
                    path.write_text(json.dumps({'main_session': {key: value}}))
                    if value is None or value == 'auto' or type(value) is int and 100000 <= value <= 1000000:
                        result = load_config(self.root, config_file=repo)
                        self.assertEqual((result.sources['main_session.' + key],
                            normalize_claude_auto_compact_window(result.effective['main_session'][key])),
                            (source, value if type(value) is int else None))
                    else:
                        with self.assertRaisesRegex(error, str(path)):
                            load_config(self.root, config_file=repo)
