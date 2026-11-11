"""Only synthetic repositories and mocked runtime inventories."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
import wt_legacy
from hand_ext import gc
from side_session import gc as side_gc


class LegacyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve(); self.repo = self.base / 'repo'; self.repo.mkdir()
        self.git('init'); self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'file').write_text('old'); self.git('add', '.'); self.git('commit', '-m', 'base')
        self.path = self.base / 'wt/legacy'; self.git('worktree', 'add', '-b', 'legacy', str(self.path))
        self.cfg = SimpleNamespace(root=self.repo, worktree_root=self.path.parent,
                                   machine_state_dir=self.base / 'state', paseo={})
        self.scan = wt_legacy.Scan()
        for target in ('side_session.checkout._cwd_clear', 'wt_legacy.shutil.which'):
            mock = patch(target, return_value=True); mock.start(); self.addCleanup(mock.stop)
        original = self.scan.command
        self.scan.command = lambda args: b'[]' if args[0] == 'paseo' else original(args)

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-C', str(cwd or self.repo), *args], check=True,
                              capture_output=True).stdout.decode().strip()

    def age(self):
        gitdir = Path(self.git('rev-parse', '--absolute-git-dir', cwd=self.path))
        for path in [*gitdir.rglob('*'), *self.path.rglob('*')]:
            if path.is_file():
                os.utime(path, (time.time() - 90000,) * 2)

    def test_recover_and_apply(self):
        self.git('checkout', '-b', 'saved'); (self.repo / 'file').write_text('saved')
        self.git('commit', '-am', 'save'); (self.path / 'file').write_text('saved')
        output = self.path / 'output/llm'; output.mkdir(parents=True)
        (output / 'report').write_text('synthetic'); self.age()
        self.assertTrue(self.scan.evaluate(self.repo, self.path)['eligible'])
        with patch.object(wt_legacy, 'Scan', return_value=self.scan), patch('pathlib.Path.home', return_value=self.base):
            rows = gc.run_gc(self.cfg, apply=True)
        self.assertTrue(rows[0]['removed']); self.assertFalse(self.path.exists())
        self.assertTrue(Path(rows[0]['backup']).is_file())
        self.assertIn('refs/heads/legacy', self.git('for-each-ref', '--format=%(refname)'))
        self.git('worktree', 'add', str(self.path), 'legacy')
        (self.path / 'file').write_text('saved'); output.mkdir(parents=True)
        (output / 'report').write_text('synthetic'); self.age()
        cfg = SimpleNamespace(repo=self.repo, state_dir=self.base / 'side-state')
        with patch.object(wt_legacy, 'Scan', return_value=self.scan), patch('pathlib.Path.home', return_value=self.base):
            report = side_gc.apply(cfg)
        row = next(row for row in report['worktrees'] if row['path'] == str(self.path))
        self.assertEqual(row['result'], 'removed'); self.assertTrue(Path(row['backup']).is_file())
        self.assertIn('refs/heads/legacy', self.git('for-each-ref', '--format=%(refname)'))

    def test_untracked_unknown(self):
        (self.path / 'unique').write_text('unique'); self.age()
        result = self.scan.evaluate(self.repo, self.path)
        self.assertFalse(result['eligible']); self.assertIn('no recoverable copy: unique', result['reason'])

    def test_detached_unreachable(self):
        self.git('checkout', '--detach', cwd=self.path)
        (self.path / 'file').write_text('orphan'); self.git('commit', '-am', 'orphan', cwd=self.path)
        self.age(); result = self.scan.evaluate(self.repo, self.path)
        self.assertFalse(result['eligible']); self.assertIn('HEAD not reachable', result['reason'])
