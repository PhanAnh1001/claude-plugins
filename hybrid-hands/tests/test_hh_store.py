"""hh_store infrastructure; synthetic temp files only."""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
import hh_store as hs

def parse(text, off, fid, gen):
    return [("codex_records", {"file_id": fid, "generation": gen, "byte_offset": off, "kind": text.strip()})]

class HhStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); os.environ[hs.paths.STATE_DIR_ENV] = str(self.tmp / "st")
        self.conn = hs.open_store(); self.log = self.tmp / "a.jsonl"

    def kinds(self):
        return [r[0] for r in self.conn.execute("SELECT kind||':'||generation FROM codex_records ORDER BY byte_offset")]

    def test_partial_line_then_rest(self):
        self.log.write_bytes(b"a\nb\nc")
        self.assertEqual(hs.read_appended(self.conn, self.log, "codex_sessions", parse), 2)
        self.assertEqual(hs.read_tail(self.conn, self.log), "c")
        with open(self.log, "ab") as fh: fh.write(b"x\n")
        hs.read_appended(self.conn, self.log, "codex_sessions", parse)
        self.assertEqual(self.kinds(), ["a:0", "b:0", "cx:0"])

    def test_truncate_and_replace_bump_generation(self):
        self.log.write_bytes(b"a\nb\n"); hs.read_appended(self.conn, self.log, "s", parse)
        self.log.write_bytes(b"z\n"); hs.read_appended(self.conn, self.log, "s", parse)
        self.assertEqual(self.kinds(), ["z:1"])
        new = self.tmp / "n"; new.write_bytes(b"q\nr\n"); os.replace(new, self.log)
        hs.read_appended(self.conn, self.log, "s", parse)
        self.assertEqual(self.kinds(), ["q:2", "r:2"])

    def test_corrupt_db_rebuilt_and_revision(self):
        self.conn.close(); db = self.tmp / "st" / hs.db.DB_NAME
        for s in ("-wal", "-shm"): Path(f"{db}{s}").unlink(missing_ok=True)
        db.write_bytes(b"garbage" * 1000)
        self.assertEqual(hs.open_store().execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "1")
        hs.bump_revision(); hs.bump_revision(); self.assertEqual(hs.read_revision(), 2)
        self.assertIsNone(hs.bump_revision(self.tmp / "missing" / "dir"))
        os.environ[hs.runtime.STORE_ENV] = "off"
        try:
            hs.runtime._reset_for_tests(); self.assertIsNone(hs.connection())
        finally:
            del os.environ[hs.runtime.STORE_ENV]; hs.runtime._reset_for_tests()

if __name__ == "__main__":
    unittest.main()
