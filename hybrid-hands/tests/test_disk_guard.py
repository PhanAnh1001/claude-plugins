import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext.disk_guard import check_disk, DiskGuardBlocked, GIB


class DiskTest(unittest.TestCase):
    def test_thresholds_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'missing'/'worktrees'
            for free, blocked, warn in [(21, False, False), (10, False, True), (4, True, False), (5, False, True)]:
                with self.subTest(free=free), patch('hand_ext.disk_guard.shutil.disk_usage',
                        return_value=SimpleNamespace(free=free*GIB)) as usage, contextlib.redirect_stderr(io.StringIO()) as out:
                    if blocked:
                        with self.assertRaises(DiskGuardBlocked): check_disk(target)
                        check_disk(target, ignore=True)
                    else:
                        check_disk(target)
                        self.assertEqual(bool(out.getvalue()), warn)
                    self.assertEqual(usage.call_args.args[0], Path(tmp).resolve())
            self.assertFalse(target.exists())

            for invalid in ([], False, 'bad', {'block_gb': True}, {'warn_gb': float('nan')},
                            {'block_gb': '1'}, {'block_gb': -1}, {'block_gb': 30}):
                with self.assertRaises(ValueError): check_disk(target, invalid)

    def test_cli_and_prepare_preflight(self):
        from dataclasses import make_dataclass
        from hand_ext import cli, isolation
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            cfg = make_dataclass('Config', ['root', 'worktree_root', 'isolation', 'isolation_explicit', 'disk_guard', 'ignore_disk_guard'])(Path(tmp), Path(tmp)/'missing', 'worktree', False, {}, False)
            with patch.object(cli, '_cfg', return_value=cfg), patch.object(isolation, 'git_root', return_value=cfg.root), patch('hand_ext.disk_guard.shutil.disk_usage', return_value=SimpleNamespace(free=GIB)), patch.dict(cli.COMMANDS, run=lambda c, a: 17), patch.object(isolation, '_git') as git:
                argv = ['run', '--brief', 'fake', '--isolation', 'worktree']
                self.assertEqual(cli.main(argv), 9)
                with self.assertRaises(DiskGuardBlocked):
                    isolation.prepare(cfg, cfg.root, 'fake', Path(tmp)/'run', isolation.IsolationChoice('worktree'))
                git.assert_not_called(); self.assertFalse(cfg.worktree_root.exists())
                self.assertEqual(cli.main(argv + ['--ignore-disk-guard']), 17)
                with patch.object(isolation, 'git_root', return_value=None):
                    self.assertEqual(cli.main(argv), 2)
