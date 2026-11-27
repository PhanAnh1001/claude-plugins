"""Profile → role table resolution, using temporary config files only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'
sys.path.insert(0, str(LIB))
from shared_config import load_config
from hand_ext.profiles import ProfileError, normalize_profile, profile_table, role_spec


class ProfilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        env = patch.dict(os.environ, HOME=str(self.root), HYBRID_HANDS_CONFIG='global.json')
        env.start()
        self.addCleanup(env.stop)

    def cfg(self, global_data=None, repo_data=None):
        (self.root / 'global.json').write_text(json.dumps(global_data or {}))
        repo = self.root / 'repo.json'
        repo.write_text(json.dumps(repo_data or {}))
        return load_config(known_root=self.root, config_file=repo).effective

    def test_default_tables(self):
        def short(spec):
            return (spec['provider'], spec['account'], spec['model'].split('-')[-1 if spec['provider'] == 'codex' else 1], spec['effort'])
        expected = {
            'claude-mono': {'brain': ('claude', 'v1', 'opus', 'high'), 'code': ('claude', 'v1', 'opus', 'low'),
                            'collect.1': ('claude', 'v1', 'sonnet', 'low'), 'collect.2': ('claude', 'v1', 'sonnet', 'medium'),
                            'chrome.1': ('claude', 'v1', 'sonnet', 'low'), 'chrome.2': ('claude', 'v1', 'sonnet', 'medium')},
            'gpt-mono': {'brain': ('codex', 'v1', 'sol', 'high'), 'code': ('codex', 'v1', 'sol', 'low'),
                         'collect.1': ('codex', 'v1', 'terra', 'low'), 'collect.2': ('codex', 'v1', 'terra', 'low'),
                         'chrome.1': ('claude', 'v2', 'sonnet', 'low'), 'chrome.2': ('claude', 'v2', 'sonnet', 'medium')},
        }
        expected['hybrid'] = {**expected['gpt-mono'], 'super': ('claude', 'v2', 'opus', 'high')}
        expected['claude-mono-v2'] = {k: (p, 'v2', m, e) for k, (p, _, m, e) in expected['claude-mono'].items()}
        expected['claude-mono-v1'] = expected['claude-mono']  # alias trong file cấu hình
        for name, table in expected.items():
            got = profile_table(self.cfg(repo_data={'profile': name}))
            self.assertEqual({k: short(v) for k, v in got.items()}, table, name)
        self.assertEqual(role_spec(self.cfg(repo_data={'profile': 'hybrid'}), 'collect')['tier'], 1)

    def test_override_precedence(self):
        glob = {'profile': 'claude-mono', 'profiles': {'claude-mono': {
            'collect': {'1': {'effort': 'high'}}, 'code': {'effort': 'medium'}}}}
        repo = {'profiles': {'claude-mono': {'collect': {'1': {'effort': 'max'}}}}}
        cfg = self.cfg(glob, repo)
        self.assertEqual(role_spec(cfg, 'collect', 1)['effort'], 'max')
        self.assertEqual(role_spec(cfg, 'code')['effort'], 'medium')
        self.assertEqual(role_spec(cfg, 'brain')['effort'], 'high')

    def test_normalize_profile(self):
        for raw, want in (('claude-mono v2', 'claude-mono-v2'), ('claude-mono-v1', 'claude-mono'),
                          ('claude-mono v1', 'claude-mono'), ('hybrid', 'hybrid')):
            self.assertEqual(normalize_profile(raw), want)
        self.assertEqual(normalize_profile('claude-mono', 'v2'), 'claude-mono-v2')
        for bad in ('gpt-mono v2', 'claude-mono v3', 'lạ'):
            with self.assertRaises(ProfileError) as ctx:
                normalize_profile(bad)
            self.assertIn('claude-mono [v1|v2]', str(ctx.exception))

    def test_errors(self):
        cases = [({}, 'brain', 'hand-ext profile set'),
                 ({'profile': 'lạ'}, 'brain', 'claude-mono'),
                 ({'profile': 'gpt-mono', 'profiles': {'gpt-mono': {'code': {'model': 'gpt-x'}}}},
                  'code', 'profiles.gpt-mono.code.model'),
                 ({'profile': 'claude-mono'}, 'super', 'super')]
        for repo, role, needle in cases:
            with self.assertRaises(ProfileError) as ctx:
                role_spec(self.cfg(repo_data=repo), role)
            self.assertIn(needle, str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
