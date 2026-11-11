"""Synthetic start preflight: no real GC or provider dispatch."""
import sys, tempfile, unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from side_session import actions, cli
from side_session.config import SideConfig
from hand_ext import disk_guard
class StartGateTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.cfg = SideConfig(self.root, self.root/'handoff', self.root/'missing'/'wt', 4, 100, 30, state_dir=self.root/'state')
    def args(self, *flags): return cli.build_parser().parse_args(['start', '--name', 'fake', '--prompt', 'synthetic', *flags])
    def test_auto_policy(self):
        with patch.object(actions.gc, 'apply', side_effect=[{'errors': []}, TypeError('synthetic'), AttributeError('synthetic'), {'errors': ['synthetic']}]) as gc, patch.object(actions, 'check_disk') as disk:
            for _ in range(4): self.assertIsNone(actions._worktree_preflight(self.cfg, self.args('--worktree')))
            self.assertGreater(gc.call_args.kwargs.pop('deadline'), 0); self.assertEqual(gc.call_args.kwargs, dict(include_unmerged=False, prune_branches=False, fetch=False))
            actions._worktree_preflight(replace(self.cfg, worktree_gc_auto='off'), self.args('--worktree')); self.assertEqual((gc.call_count, disk.call_count), (4, 5))
    def test_disk_thresholds(self):
        with patch.object(disk_guard.shutil, 'disk_usage') as usage:
            for free, override, expected in [(4, False, 9), (10, False, None), (4, True, None)]:
                usage.return_value.free = free * disk_guard.GIB; args = self.args('--worktree'); args.ignore_disk_guard = override
                self.assertEqual(actions._worktree_preflight(replace(self.cfg, worktree_gc_auto='off'), args), expected); self.assertEqual(usage.call_args.args, (self.root,))
    def test_start_gate(self):
        with patch.object(actions.gc, 'apply') as gc, patch.object(actions, 'check_disk', side_effect=disk_guard.DiskGuardBlocked('synthetic')), patch.object(actions, '_preflight', return_value=None), patch.object(actions.paseo, 'plan', return_value=None) as plan, patch.object(actions, 'resume', return_value=0), patch.object(actions, '_launch', return_value=0), patch.object(actions.paseo, 'start_session', return_value=0):
            for flags in [('--worktree',), ('--worktree', '--dry-run'), ('--resume',), ()]:
                plan.reset_mock(); gc.reset_mock(); self.assertEqual(actions.start(self.cfg, self.args(*flags)), 9 if flags == ('--worktree',) else 0); self.assertEqual(gc.call_count, int(flags == ('--worktree',)))
                if flags == ('--worktree',):
                    self.assertEqual(actions.start(replace(self.cfg, transport='screen'), self.args(*flags)), 9); plan.assert_not_called()
            self.assertFalse(self.cfg.state_dir.exists() or self.cfg.worktree_root.parent.exists())
