"""Checkout lifecycle with synthetic git repositories only."""
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from side_session import checkout, state, constants as C


class CheckoutTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('commit', '--allow-empty', '-m', 'initial')
        self.cfg = SimpleNamespace(repo=self.repo, worktree_root=self.root / 'repo-wt',
                                   state_dir=self.root / 'state')
        self.path = self.cfg.worktree_root / 'test'
        self.st = state.SessionState('test', 'fixture', 'claude', str(self.path), '', '',
                                     100, 0, C.STATUS_DONE, '', worktree=True)
        checkout.intent(self.cfg, self.st)
        self.git('worktree', 'add', '-b', self.st.checkout_branch, str(self.path))
        checkout.created(self.cfg, self.st)
        for target, value in [('side_session.checkout._cwd_clear', None),
                              ('side_session.checkout.Path.home', self.root)]:
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       stderr=subprocess.DEVNULL)

    def test_done_unmerged_backup_and_branch(self):
        subprocess.check_call(['git', '-C', str(self.path), 'commit', '--allow-empty',
                               '-m', 'unmerged'], stdout=subprocess.DEVNULL)
        output = self.path / 'output/llm'
        output.mkdir(parents=True)
        (output / 'fixture.txt').write_text('public fixture')
        checkout.remove_done(self.cfg, self.st)
        self.assertFalse(self.path.exists())
        self.assertTrue(self.st.checkout_removed_at)
        self.git('show-ref', '--verify', 'refs/heads/' + self.st.checkout_branch)
        with tarfile.open(self.st.checkout_backup) as archive:
            self.assertEqual(archive.extractfile('output/llm/fixture.txt').read(), b'public fixture')

    def test_done_dirty_kept(self):
        (self.path / 'uncommitted').write_text('fixture')
        checkout.remove_done(self.cfg, self.st)
        self.assertTrue(self.path.exists())
        self.assertIn('untracked', self.st.checkout_reason)

    def test_restore_before_followup(self):
        checkout.remove_done(self.cfg, self.st)
        self.assertTrue(checkout.restore(self.cfg, self.st))
        self.assertEqual(subprocess.check_output(['git', '-C', str(self.path),
                         'branch', '--show-current']).decode().strip(), self.st.checkout_branch)
        self.assertIsNone(state.load(self.cfg.state_dir, 'test').checkout_removed_at)
