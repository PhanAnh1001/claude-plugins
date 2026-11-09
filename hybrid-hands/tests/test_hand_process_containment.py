"""Synthetic OS boundaries and finite owned subprocesses; no host env scan."""
import dataclasses
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext.process_containment import Descendants, OSIdentity, ProcessTable, procargs_marker, METHOD
from hand_ext.execution_worker import OwnedProcessOps


class ContainmentTests(unittest.TestCase):
    def test_exact_marker_protection_reparent_reuse_and_unknown(self):
        uid = os.getuid()
        root = OSIdentity(70001, 'a', 'root', os.getpid(), uid)
        child = OSIdentity(70002, 'b', 'child', root.pid, uid)
        escaped = OSIdentity(70003, 'c', 'escape', 1, uid)
        owner = OSIdentity(os.getpid(), 'o', 'owner', 1, uid)
        class Table:
            rows = {i.pid: i for i in (root, child, escaped, owner)}
            calls = []
            error = False
            def snapshot(self): return self.rows.copy()
            def marker_matches(self, pid, invocation):
                if self.error: raise RuntimeError('SECRET_SENTINEL')
                return pid in (escaped.pid, owner.pid) or (pid == child.pid and self.rows[pid].start == child.start)
            def signal(self, item, sig):
                if item.matches(self.rows.get(item.pid)): self.calls.append((item.pid, sig))
        table = Table()
        proc = type('Proc', (), {'pid': root.pid, 'returncode': None})()
        tree = Descendants(proc, 'fixture', table)
        key = (child.pid, child.start, child.comm, child.uid)
        initial = tree.ancestry[key][0]
        self.assertEqual(initial, (child, root, owner))
        table.rows.pop(root.pid); proc.returncode = 0
        table.rows[child.pid] = dataclasses.replace(child, ppid=1)
        tree.signal_live(signal.SIGTERM)
        self.assertEqual(tree.ancestry[key][0], initial)
        self.assertEqual(tree.ancestry[key][-1], (table.rows[child.pid],))
        self.assertEqual({pid for pid, _ in table.calls}, {child.pid, escaped.pid})
        table.rows[child.pid] = dataclasses.replace(child, start='REUSED', ppid=1)
        table.rows[70004] = OSIdentity(70004, 'd', 'unowned', child.pid, uid)
        table.calls.clear(); tree.signal_live(signal.SIGKILL)
        self.assertEqual(table.calls, [(escaped.pid, signal.SIGKILL)])
        self.assertNotIn(70004, tree.tracked)
        self.assertFalse(tree.verify())
        table.rows.pop(escaped.pid); self.assertTrue(tree.verify())
        table.error = True; self.assertFalse(tree.verify())
        table.error = False
        # Real signal boundary must reject a reused PID, independent of tracker.
        with patch.object(ProcessTable, 'identity', return_value=table.rows.get(child.pid)), patch('os.kill') as kill:
            ProcessTable().signal(child, signal.SIGKILL)
            kill.assert_not_called()
        # Bounded cancellation keeps unknown for an unkillable marked child.
        table.rows[root.pid] = root; table.rows[escaped.pid] = escaped
        proc.returncode = 0
        proc.poll = lambda: proc.returncode
        proc.wait = lambda timeout: proc.returncode
        ops = OwnedProcessOps(table=table); identity = ops.add(proc, 'fixture')
        table.rows.pop(root.pid)
        with patch('os.killpg', side_effect=ProcessLookupError), patch('hand_ext.execution_worker.TERM_WAIT', 0), patch('hand_ext.execution_worker.VERIFY_WAIT', 0):
            self.assertFalse(ops.cancel(identity, 'fixture').confirmed)
            table.rows.pop(escaped.pid)
            self.assertTrue(ops.reconcile(identity).confirmed)
        table.rows[root.pid] = root; proc.returncode = None
        lost = Descendants(proc, 'fixture', table)
        table.rows[root.pid] = dataclasses.replace(root, start='REUSED')
        lost.capture(); self.assertFalse(lost.authoritative)
        self.assertNotIn('SECRET_SENTINEL', repr(tree.__dict__))
        marker = b'HYBRID_HANDS_INVOCATION_ID=fixture'
        def args(argv, env):
            return (len(argv)).to_bytes(4, sys.byteorder) + b'/exe\0\0' + b'\0'.join(argv + env) + b'\0'
        self.assertFalse(procargs_marker(args([b'exe', marker], [b'SECRET=sentinel']), marker))
        self.assertTrue(procargs_marker(args([b'exe'], [marker, b'SECRET=sentinel']), marker))
        self.assertFalse(procargs_marker(args([b'exe'], [marker + b'-other']), marker))
        with patch('hand_ext.process_containment.Path.read_bytes', side_effect=PermissionError('SECRET_SENTINEL')), patch('hand_ext.process_containment.sys.platform', 'linux'):
            with self.assertRaisesRegex(RuntimeError, '^marker scan unavailable$'):
                ProcessTable().marker_matches(123, 'fixture')

    def test_raced_marker_exit_exec_and_unreadable_diagnostics(self):
        uid = os.getuid()
        root = OSIdentity(80001, '10', 'before-exec', 1, uid)
        raced = OSIdentity(80002, '11', 'raced', 1, uid)
        child = OSIdentity(80003, '12', 'escaped', 1, uid)
        class Table:
            rows = {i.pid: i for i in (root, raced, child)}
            mode = 'gone'
            def snapshot(self): return self.rows.copy()
            def identity(self, pid):
                if pid == raced.pid and self.mode == 'gone': return None
                if pid == raced.pid and self.mode == 'reused':
                    return dataclasses.replace(raced, start='99')
                return self.rows.get(pid)
            def marker_matches(self, pid, invocation):
                if pid == raced.pid:
                    if self.mode == 'gone': raise OSError(22, 'SECRET_SENTINEL')
                    raise PermissionError('SECRET_SENTINEL')
                return pid == child.pid
        table = Table()
        proc = type('Proc', (), {'pid': root.pid, 'returncode': None})()
        tree = Descendants(proc, 'fixture', table)
        self.assertEqual({i.pid for i in tree.live()}, {child.pid})
        self.assertTrue(tree.authoritative)
        self.assertEqual(tree.details()['diagnostics'][-1]['error'], 'einval')
        self.assertEqual(tree.details()['diagnostics'][-1]['resolution'], 'gone_or_reused')
        for _ in range(70): tree.live()
        table.mode = 'reused'; tree.live(); self.assertTrue(tree.authoritative)
        table.rows[root.pid] = dataclasses.replace(root, comm='after-exec')
        tree.capture(); self.assertTrue(tree.authoritative)
        with patch.object(ProcessTable, 'identity', return_value=table.rows[root.pid]), patch('os.kill') as kill:
            ProcessTable().signal(root, signal.SIGTERM)
            kill.assert_called_once_with(root.pid, signal.SIGTERM)
        table.mode = 'unreadable'; tree.live(); self.assertFalse(tree.authoritative)
        details = tree.details()
        self.assertEqual(details['first_fatal']['pid'], raced.pid)
        self.assertEqual(details['first_fatal']['start'], raced.start)
        self.assertEqual(details['first_fatal']['stage'], 'marker')
        self.assertEqual(details['method'], METHOD)
        self.assertNotIn('SECRET_SENTINEL', repr(details))
        from hand_ext.process_containment import merge_evidence
        merged = merge_evidence(details, dict(diagnostics=[], first_fatal=None, inventory_complete=True))
        self.assertEqual(merged['first_fatal'], details['first_fatal'])
        self.assertFalse(merged['inventory_complete'])
        table.rows.pop(raced.pid); tree.live(); self.assertFalse(tree.authoritative)

    def test_owned_setsid_descendant_after_root_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'child'
            code = ('import subprocess,sys,time; from pathlib import Path; '
                    'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(15)"],'
                    'start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); '
                    f'Path({str(path)!r}).write_text(str(p.pid)); time.sleep(.4)')
            proc = subprocess.Popen([sys.executable, '-c', code], start_new_session=True,
                                    env={'HYBRID_HANDS_INVOCATION_ID': 'synthetic-fixture'})
            table = ProcessTable()
            # Marker lookup is a fixture map; never read other host environments.
            table.marker_matches = lambda pid, invocation: path.exists() and pid == int(path.read_text())
            ops = OwnedProcessOps(table=table)
            identity = ops.add(proc, 'synthetic-fixture')
            child = child_identity = None
            try:
                for _ in range(40):
                    ops.capture(identity)
                    if path.exists():
                        child = int(path.read_text())
                        child_identity = table.snapshot().get(child) or child_identity
                    if proc.poll() is not None: break
                    time.sleep(.025)
                self.assertIsNotNone(child)
                self.assertIsNotNone(proc.returncode)
                self.assertFalse(ops.reconcile(identity).confirmed)
                q = ops.cancel(identity, 'fixture cancel')
                self.assertTrue(q.confirmed, q)
                self.assertEqual(q.evidence, METHOD)
                self.assertFalse(OwnedProcessOps().cancel(identity, 'restart').confirmed)
            finally:
                if proc.poll() is None: proc.kill()
                proc.wait(timeout=2)
                if child_identity:
                    try: table.signal(child_identity, signal.SIGKILL)
                    except ProcessLookupError: pass


if __name__ == '__main__': unittest.main()
