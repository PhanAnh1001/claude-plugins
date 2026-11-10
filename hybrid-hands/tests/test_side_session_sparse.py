"""Sparse worktree creation for side-session start (fake git repo under a tempdir)."""
import dataclasses
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from side_session import commands as K
from side_session import paseo
from side_session.cli import build_parser
from side_session.config import SideConfig, _sparse_exclude

GIT_ENV = {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.invalid',
           'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@example.invalid'}


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout


class SparseWorktreeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        patcher = patch.dict(os.environ, GIT_ENV); patcher.start(); self.addCleanup(patcher.stop)
        self.repo = Path(tmp.name) / 'repo'
        self.cfg = SideConfig(repo=self.repo, handoff_dir=self.repo, worktree_root=Path(tmp.name) / 'wt',
                              max_parallel=1, default_max_tokens=1, watch_interval_s=1,
                              worktree_sparse_exclude=('big/*-data/',))

    def test_sparse_excludes_pattern_only_in_new_worktree(self):
        (self.repo / 'big/x-data').mkdir(parents=True); (self.repo / 'big/x-data/f').write_text('1')
        (self.repo / 'keep').write_text('1')
        git('-C', str(self.repo), 'init', '-q'); git('-C', str(self.repo), 'add', '.')
        git('-C', str(self.repo), 'commit', '-qm', 'init')
        self.assertEqual(K.run_worktree_steps(K.worktree_steps(self.cfg, 's', 'HEAD')), 0)
        wt = self.cfg.worktree_root / 's'
        self.assertTrue((wt / 'keep').exists()); self.assertFalse((wt / 'big/x-data/f').exists())
        self.assertTrue((self.repo / 'big/x-data/f').exists())
        self.assertEqual(git('-C', str(self.repo), 'status', '--porcelain'), '')
        self.assertNotIn('sparse', git('config', '--file', str(self.repo / '.git/config'), '--list'))

    def test_default_and_no_sparse_keep_single_add(self):
        plain = dataclasses.replace(self.cfg, worktree_sparse_exclude=())
        for cfg, sparse in ((plain, True), (self.cfg, False)):
            steps = K.worktree_steps(cfg, 's', 'HEAD', sparse=sparse)
            self.assertEqual([s.argv for s in steps], [K.worktree_cmd(cfg, 's', 'HEAD')])
        self.assertTrue(build_parser().parse_args(['start', '--name', 'n', '--no-sparse']).no_sparse)

    def test_paseo_uses_shared_steps_and_bad_patterns_rejected(self):
        a = build_parser().parse_args(['start', '--name', 's', '--worktree'])
        st = type('St', (), {'role': 'main', 'name': 's'})()
        with patch.object(K, 'run_worktree_steps', return_value=1) as run:
            self.assertEqual(paseo.start_session(self.cfg, a, st, '', '', ''), 1)
        argvs = [s.argv for s in run.call_args.args[0]]
        self.assertIn('--no-checkout', argvs[0]); self.assertEqual(argvs[2][-1], 'checkout')
        for bad in (['!x'], [''], ['a\nb'], 'x'):
            with self.assertRaises(ValueError):
                _sparse_exclude(bad)


if __name__ == '__main__':
    unittest.main()
