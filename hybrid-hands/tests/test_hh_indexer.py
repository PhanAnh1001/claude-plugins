"""hh-indexer singleton, one ingest cycle, idle exit/SIGTERM; temp HOME + state only."""
import json, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hh_ps_gpt_nguon import NOW, event, write
from hh_store import cli, indexer, paths, runtime

BIN = Path(cli.INDEXER_BIN)


class IndexerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.state = self.tmp / "st"
        env = {"HOME": str(self.tmp), "HYBRID_HANDS_STATE_DIR": str(self.state),
               runtime.STORE_ENV: "on", cli.INDEXER_ENV: "on"}  # independent of the outer env
        self.env = patch.dict(os.environ, env); self.env.start(); runtime._reset_for_tests()
        self.addCleanup(self.env.stop); self.addCleanup(runtime._reset_for_tests)

    def daemon(self, *args):
        proc = subprocess.Popen([sys.executable, str(BIN), *args], env=dict(os.environ))
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        for _ in range(60):
            if cli.indexer_running(paths.state_dir()):
                return proc
            time.sleep(0.05)
        self.fail("indexer did not take the lock")

    def test_singleton_touch_and_sigterm(self):
        first = self.daemon("--idle-timeout", "30")
        second = subprocess.run([sys.executable, str(BIN)], env=dict(os.environ), timeout=5)
        self.assertEqual(second.returncode, 0)
        with patch.object(cli.subprocess, "Popen") as popen:
            cli.touch(["/x.jsonl"])
        popen.assert_not_called()
        self.assertTrue((self.state / paths.LAST_READ_NAME).exists())
        first.send_signal(signal.SIGTERM)
        self.assertEqual(first.wait(5), 0)
        self.assertFalse(cli.indexer_running(self.state))

    def test_idle_exit(self):
        proc = self.daemon("--idle-timeout", "0.5", "--active-poll", "0.1")
        self.assertEqual(proc.wait(5), 0)
        self.assertFalse(cli.indexer_running(self.state))

    def test_ingest_cycle_revision_and_rewrite(self):
        path = self.tmp / ".codex-hand" / "sessions" / "rollout-t.jsonl"
        path.parent.mkdir(parents=True)
        write(path, [event(NOW - 200, count=100)])
        self.assertTrue(indexer.ingest_once([path], full=True))
        rev = paths.read_revision()
        self.assertFalse(indexer.ingest_once([path]))
        self.assertEqual(paths.read_revision(), rev)
        with open(path, "a") as fh:
            fh.write(json.dumps(event(NOW - 100, count=150)) + "\n")
        self.assertTrue(indexer.ingest_once([path]))
        self.assertEqual(paths.read_revision(), rev + 1)
        with open(path, "a") as fh:  # a reader (hh-ps) ingests the append before us
            fh.write(json.dumps(event(NOW - 90, count=160)) + "\n")
        from hh_ps.native_source import _classify
        from hh_store import codex_ingest
        codex_ingest.records(path, _classify); runtime.release()
        self.assertTrue(indexer.ingest_once([path]))  # still bumps for the other readers
        moved = path.with_name("rollout-u.jsonl"); path.rename(moved)
        write(path, [event(NOW - 50, count=10)])  # new inode at the old path
        self.assertTrue(indexer.ingest_once([path]))  # rewrite: old rows dropped (phase 1)
        rows = runtime.connection().execute("SELECT count(*) FROM codex_records r JOIN files f"
                                            " USING (file_id) WHERE f.path=?", (str(path),))
        self.assertEqual(rows.fetchone()[0], 1); runtime.release()

    def test_full_scan_skips_vanished_rollout(self):
        path = self.tmp / ".codex-hand" / "sessions" / "rollout-t.jsonl"
        path.parent.mkdir(parents=True)
        write(path, [event(NOW - 200, count=100)])
        from hh_ps import machine_usage
        with patch.object(machine_usage, "_machine_rollouts",
                          return_value=[path.with_name("rollout-gone.jsonl"), path]):
            self.assertTrue(indexer.ingest_once(full=True))

    def test_main_maps_flags_by_name(self):
        with patch.object(indexer, "run", side_effect=lambda cfg: cfg) as run:
            indexer.main(["--rollout-scan", "300", "--active-poll", "2"])
        cfg = run.call_args[0][0]
        self.assertEqual((cfg.rollout_scan, cfg.active_poll), (300.0, 2.0))


if __name__ == "__main__":
    unittest.main()
