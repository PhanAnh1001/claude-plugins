"""Store-backed rollout readers equal the legacy file path; synthetic files only."""
import json, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hh_ps_gpt_nguon import NOW, event, iso, write
from hh_store import codex_ingest, runtime
from hh_ps import native_source
from hh_ps.machine_usage import _gpt_usd


class StoreCodexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = patch.dict(os.environ, {"HYBRID_HANDS_STATE_DIR": str(self.tmp / "st")})
        self.env.start(); runtime._reset_for_tests()
        self.addCleanup(self.env.stop); self.addCleanup(runtime._reset_for_tests)
        self.home = self.tmp / "home"; self.root = self.home / "sessions"; self.root.mkdir(parents=True); self.home = self.home.resolve(); self.root = self.root.resolve()
        self.path = (self.root / "rollout-t.jsonl").resolve()
        meta = {"type": "session_meta", "payload": {"id": "t", "parent_thread_id": "p",
                "model": "gpt-6.1-sol", "timestamp": iso(NOW - 250)}}
        write(self.path, [meta, event(NOW - 200, count=100)])

    def both(self):
        """(store on, store off) results of machine USD~ and native child usage."""
        out = []
        for store in ("on", "off"):
            with patch.dict(os.environ, {"HYBRID_HANDS_STORE": store}):
                runtime._reset_for_tests()
                child = native_source._read(self.path, NOW)[2]
                out.append((_gpt_usd(SimpleNamespace(home=self.home), None, NOW - 300, NOW),
                            child.usage, child.status))
        runtime._reset_for_tests()
        return out

    def test_append_between_runs_and_parse_counter(self):
        on, off = self.both(); self.assertEqual(on, off)
        with open(self.path, "a") as fh:  # complete line, then a tail without newline
            fh.write(json.dumps(event(NOW - 100, count=150)) + "\n" + json.dumps(event(NOW - 50, count=170)))
        calls = []
        real = native_source._classify
        with patch.object(native_source, "_classify", side_effect=lambda l: calls.append(l) or real(l)):
            on2, off2 = self.both()
        self.assertEqual(on2, off2); self.assertNotEqual(on2[0], on[0])
        self.assertEqual(len(calls), 2)  # only the appended line and the tail, not the old rows

    def test_moved_to_archive_not_double_counted(self):
        expected = self.both()[0][0]
        archive = self.home / "archived_sessions"; archive.mkdir()
        os.replace(self.path, archive / self.path.name)
        self.assertEqual(_gpt_usd(SimpleNamespace(home=self.home), None, NOW - 300, NOW), expected)
        files = runtime.connection().execute("SELECT scope FROM files").fetchall()
        self.assertEqual(files, [("codex_archived",)])

    def test_strict_bad_line_matches_legacy(self):
        with open(self.path, "a") as fh:
            fh.write('{"type": "event_msg", "payload": {"type": "token_count", broken\n')
        on, off = self.both()
        self.assertEqual(on, off); self.assertIsNone(on[0])
        self.assertIsNotNone(on[1])  # non-strict native reader skips the bad line

    def test_unchanged_file_no_writes_rewrite_still_detected(self):
        first = codex_ingest.records(self.path, native_source._classify)
        runtime._reset_for_tests(); conn = runtime.connection(); before = conn.total_changes
        self.assertEqual(codex_ingest.records(self.path, native_source._classify), first)
        self.assertEqual(conn.total_changes, before)  # new connection, unchanged file: no writes
        head, _, rest = self.path.read_bytes().rpartition(b"100"); self.path.write_bytes(head + b"101" + rest)
        os.utime(self.path, ns=(1, 1))  # same inode and size, mtime changed
        self.assertNotEqual(codex_ingest.records(self.path, native_source._classify), first)


if __name__ == "__main__":
    unittest.main()
