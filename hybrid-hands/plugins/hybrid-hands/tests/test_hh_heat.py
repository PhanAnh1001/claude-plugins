import io
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from hh_heat import cli


def hold_lock(path, ready):
    with open(path, 'a') as handle:
        cli.acquire_lock(handle, time.monotonic() + 3)
        ready.set()
        time.sleep(0.3)


class HeatTests(unittest.TestCase):
    def test_reap_selection(self):
        rows = [dict(pid=i, ppid=1, age=700, command=cmd) for i, cmd in enumerate([
            'Google Chrome --headless=new --user-data-dir=/tmp/test --remote-debugging-port=9344',
            'Google Chrome --user-data-dir=/tmp/test',
            'Google Chrome --headless --user-data-dir=/tmp/test --remote-debugging-port=9345'])]
        with patch.object(cli.subprocess, 'run', side_effect=[
                cli.subprocess.CompletedProcess([], 1, '', ''),
                cli.subprocess.CompletedProcess([], 0, '123\n', '')]):
            self.assertEqual([r['pid'] for r in cli.eligible(rows, 600)], [0])

    def test_gate(self):
        for cpu, expected in [(60, 1), (59, 0)]:
            with patch.object(cli, 'status', return_value={'state': cli.classify(cpu, 60)}):
                self.assertEqual(cli.gate(60, False, time.monotonic()), expected)

    def test_browser_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'browser.lock')
            ready = multiprocessing.Event()
            child = multiprocessing.Process(target=hold_lock, args=(path, ready))
            child.start()
            try:
                self.assertTrue(ready.wait(3))
                started = time.monotonic()
                with open(path, 'a') as handle:
                    cli.acquire_lock(handle, started + 3)
                    self.assertGreaterEqual(time.monotonic() - started, 0.2)
            finally:
                child.join(3)
                if child.is_alive():
                    child.terminate()
                    child.join()

    def test_browser_cleans_new_detached_only(self):
        old = dict(pid=20, ppid=1, pgid=20, age=700, command=
                   'Google Chrome --headless --user-data-dir=/tmp/heat --remote-debugging-port=9344')
        new = dict(old, pid=21, pgid=21)
        gui = dict(old, pid=22, command='Google Chrome --user-data-dir=/tmp/gui')
        child = unittest.mock.Mock(pid=99)
        child.wait.return_value = child.poll.return_value = 0
        with tempfile.TemporaryDirectory() as directory, patch.object(cli.Path, 'home', return_value=Path(directory)), \
             patch.object(cli, 'gate', return_value=0), patch.object(cli.subprocess, 'Popen', return_value=child), \
             patch.object(cli, 'processes', side_effect=[[old], [old, new, gui], [old, new, gui], [old, new, gui]]), \
             patch.object(cli, 'no_clients', return_value=True), patch.object(cli.os, 'kill') as kill, \
             patch.object(cli.os, 'killpg', side_effect=ProcessLookupError):
            # eligible's default is bound at definition time.
            with patch.object(cli.subprocess, 'run', return_value=cli.subprocess.CompletedProcess([], 1, '', '')):
                self.assertEqual(cli.browser(['fake-command'], 1), 0)
            kill.assert_called_once_with(21, cli.signal.SIGTERM)

    def test_permission_error(self):
        for action in ('status', 'reap', 'browser'):
            with patch.object(sys, 'argv', ['hh-heat', action]), patch.object(cli, action, side_effect=PermissionError), \
                 patch.object(sys, 'stderr', new_callable=io.StringIO) as error:
                self.assertEqual(cli.main(), 3)
                self.assertIn('cần chạy ngoài sandbox', error.getvalue())
