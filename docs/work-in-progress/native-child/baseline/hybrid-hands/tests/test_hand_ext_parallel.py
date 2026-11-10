"""Three behavioral checks for per-session cross-process hand slots."""
import argparse
import selectors
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"
sys.path.insert(0, str(LIB))
from hand_ext import config, parallel, run_cmd
from hand_ext.constants import DEFAULTS

WORKER = """
import sys
from pathlib import Path
from hand_ext.parallel import reserve_slot, ParallelFull
try:
    with reserve_slot(Path(sys.argv[1]), 4):
        print('held', flush=True)
        sys.stdin.read()
except ParallelFull:
    print('full', flush=True)
"""


class ParallelTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(mock.patch.dict(os.environ, {
            parallel.HAND_SCOPE_ENV: str(self.root)}))

    def test_default_four_and_fifth_rejected_before_backend_or_worktree(self):
        self.assertEqual(DEFAULTS['max_parallel'], 4)
        cfg = argparse.Namespace(root=self.root, max_parallel=4)
        for _ in range(4):
            self.stack.enter_context(parallel.reserve_slot(self.root, 4))
        err = io.StringIO()
        with mock.patch.object(run_cmd, '_cmd_run') as backend, redirect_stderr(err):
            self.assertEqual(run_cmd.cmd_run(cfg, argparse.Namespace()), 8)
        backend.assert_not_called()
        self.assertIn('đã đủ 4', err.getvalue())

    def test_release_success_error_death_and_concurrent_acquire(self):
        cfg = argparse.Namespace(root=self.root, max_parallel=1)
        with mock.patch.object(run_cmd, '_cmd_run', return_value=0):
            self.assertEqual(run_cmd.cmd_run(cfg, argparse.Namespace()), 0)
        with mock.patch.object(run_cmd, '_cmd_run', side_effect=RuntimeError('fake backend')):
            with self.assertRaises(RuntimeError):
                run_cmd.cmd_run(cfg, argparse.Namespace())
        with parallel.reserve_slot(self.root, 1):
            pass
        env = dict(os.environ, PYTHONPATH=str(LIB))
        children = []
        try:
            for _ in range(5):
                children.append(subprocess.Popen(
                    [sys.executable, '-u', '-c', WORKER, str(self.root)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env))
            # communicate(timeout) bounds readiness and lifetime even on lock regressions.
            with selectors.DefaultSelector() as ready:
                for child in children:
                    ready.register(child.stdout, selectors.EVENT_READ)
                results = {}
                for _ in children:
                    events = ready.select(timeout=10)
                    self.assertTrue(events, 'worker readiness timeout')
                    stream = events[0][0].fileobj
                    results[stream] = stream.readline().strip()
                    ready.unregister(stream)
            self.assertEqual(sorted(results.values()), ['full'] + ['held'] * 4)
            victim = next(child for child in children if results[child.stdout] == 'held')
            victim.kill()
            victim.wait(timeout=10)
            with parallel.reserve_slot(self.root, 4):
                pass
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def test_independent_scopes_and_config_validation(self):
        with mock.patch.object(config, '_read_section', return_value={}):
            self.assertEqual(config.load_config(self.root).max_parallel, 4)
        for limit in (1, 2, 3, 4, True, False, 0, 5, 1.5, '4', None):
            with mock.patch.object(config, '_read_section', return_value={'max_parallel': limit}):
                if type(limit) is int and 1 <= limit <= 4:
                    self.assertEqual(config.load_config(self.root).max_parallel, limit)
                else:
                    with self.assertRaisesRegex(ValueError, 'ext_hand.max_parallel'):
                        config.load_config(self.root)
        with parallel.reserve_slot(self.root, 1):
            with mock.patch.dict(os.environ, {parallel.HAND_SCOPE_ENV: 'other-' + str(self.root)}):
                with parallel.reserve_slot(self.root, 1):
                    pass
