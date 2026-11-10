"""`claude-tee` giữ nguyên stdout stream-json và ghi mẫu rate limit; `live_rate` đọc mẫu."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
LIB = TESTS.parent / "plugins" / "hybrid-hands" / "lib"
WRAPPER = TESTS.parent / "plugins" / "hybrid-hands" / "bin" / "claude-tee"
sys.path.insert(0, str(LIB))

from hh_ps.live_rate import read_live_window  # noqa: E402

EVENT = (
    b'{"type":"rate_limit_event","rate_limit_info":{"status":"allowed",'
    b'"resetsAt":1794549600,"rateLimitType":"seven_day","unifiedWindows":'
    b'{"seven_day":{"utilization":0.15,"resetsAt":1794549600,"status":"allowed"}}},'
    b'"uuid":"u-1","session_id":"s-1"}\n'
)
STREAM = (
    b'{"type":"system","subtype":"init"}\n'
    b'{"type":"assistant","message":{"content":[]}}\n' + EVENT +
    b'{"type":"result","subtype":"success"}'
)
FAKE = """#!/usr/bin/env python3
import sys
if "--version" in sys.argv[1:]:
    sys.stdout.write("2.1.0 (Claude Code)\\n")
    raise SystemExit(0)
sys.stdout.buffer.write(SYS_STREAM)
sys.stdout.buffer.flush()
raise SystemExit(3)
""".replace("SYS_STREAM", repr(STREAM))


class ClaudeTeeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "claude"
        self.home.mkdir()
        self.fake = base / "claude-real"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.fake.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_wrapper(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HH_CLAUDE_REAL"] = str(self.fake)
        env["CLAUDE_CONFIG_DIR"] = str(self.home)
        return subprocess.run(
            [sys.executable, str(WRAPPER), *args],
            capture_output=True, env=env, check=False)

    def test_tee_preserves_bytes_records_window_and_exit_code(self) -> None:
        result = self.run_wrapper("--output-format", "stream-json")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(result.stdout, STREAM)
        state_path = self.home / ".hh-claude-rate-limit.json"
        text = state_path.read_text(encoding="utf-8")
        self.assertEqual(json.loads(text)["windows"]["seven_day"]["utilization"], 0.15)
        self.assertNotIn("session_id", text)
        self.assertNotIn("s-1", text)

    def test_version_is_passed_through(self) -> None:
        result = self.run_wrapper("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"2.1.0 (Claude Code)\n")

    def test_read_live_window_pct_and_expired_reset(self) -> None:
        state = self.home / ".hh-claude-rate-limit.json"
        now = 1_800_000_000.0
        state.write_text(json.dumps({
            "version": 1, "updated_at": now,
            "windows": {"seven_day": {
                "utilization": 0.15, "resets_at": now + 60, "ts": now}},
        }), encoding="utf-8")
        sample = read_live_window(self.home, "seven_day", now)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.pct, 15.0)
        self.assertEqual(sample.resets_at, now + 60)
        state.write_text(json.dumps({
            "version": 1, "updated_at": now,
            "windows": {"seven_day": {
                "utilization": 0.15, "resets_at": now - 1, "ts": now}},
        }), encoding="utf-8")
        self.assertIsNone(read_live_window(self.home, "seven_day", now))


if __name__ == "__main__":
    unittest.main()
