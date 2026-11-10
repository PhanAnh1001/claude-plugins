"""hh-store-touch-hook.sh: fast silent exit 0, dirty path queued; indexer kept out by holding its lock."""
import fcntl, os, subprocess, tempfile, time, unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/scripts/hh-store-touch-hook.sh"


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve(); self.state = self.tmp / "st"; self.state.mkdir()
        self.env = {**os.environ, "HOME": str(self.tmp), "HYBRID_HANDS_STATE_DIR": str(self.state)}
        lock = os.open(self.state / "indexer.lock", os.O_RDWR | os.O_CREAT)  # held => no spawn
        fcntl.flock(lock, fcntl.LOCK_EX); self.addCleanup(os.close, lock)

    def run_hook(self, stdin):
        start = time.monotonic()
        out = subprocess.run([str(HOOK)], input=stdin, capture_output=True, env=self.env, timeout=5)
        self.assertEqual((out.returncode, out.stdout, out.stderr), (0, b"", b""))
        return time.monotonic() - start

    def wait_for(self, pred):
        for _ in range(40):
            if pred(): return True
            time.sleep(0.05)
        return False

    def test_valid_payload_queues_transcript(self):
        tr = self.tmp / "t.jsonl"; tr.write_text("{}\n")
        self.assertLess(self.run_hook(f'{{"transcript_path": "{tr}"}}'.encode()), 0.05)
        dirty = self.state / "dirty"
        self.assertTrue(self.wait_for(lambda: dirty.is_dir() and any(dirty.iterdir())))
        self.assertEqual([p.read_text() for p in dirty.iterdir()], [f"{tr}\n"])

    def test_broken_payload_still_touches(self):
        self.run_hook(b"{not json")
        self.assertTrue(self.wait_for((self.state / "last_read").exists))
