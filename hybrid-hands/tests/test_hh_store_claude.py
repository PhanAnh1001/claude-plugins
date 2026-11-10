"""hh-store Claude ingest: equivalence with the file reader, per-account rows/calibration."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hh_ps import claude_calibration as cal  # noqa: E402
from hh_ps.models import Usage  # noqa: E402
from hh_ps.transcript_source import load_subagents, parse_transcript  # noqa: E402
from hh_store import claude_ingest, runtime  # noqa: E402

MODEL = "claude-opus-5-5"


def line(mid, rid, out, ts="2026-11-10T01:00:00Z", newline=True):
    text = json.dumps({"type": "assistant", "timestamp": ts, "requestId": rid, "cwd": "/w",
                       "message": {"id": mid, "model": MODEL,
                                   "usage": {"input_tokens": 10, "output_tokens": out}}})
    return text + ("\n" if newline else "")


class ClaudeStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        config = self.root / "config.json"
        config.write_text(json.dumps({"ext_hand": {"claude_accounts": {
            "v1": {"config_dir": str(self.root / "h1")},
            "v2": {"config_dir": str(self.root / "h2")}}}}))
        env = patch.dict(os.environ, {"HYBRID_HANDS_STATE_DIR": str(self.root / "state"),
                                      "HYBRID_HANDS_CONFIG": str(config)})
        env.start()
        self.addCleanup(env.stop)
        runtime._reset_for_tests()
        self.addCleanup(runtime._reset_for_tests)

    def transcript(self, home):
        path = self.root / home / "projects" / "-w" / "s1.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def both_modes(self, read):
        stored = read()
        with patch.dict(os.environ, {"HYBRID_HANDS_STORE": "off"}):
            runtime._reset_for_tests()
            legacy = read()
        runtime._reset_for_tests()
        return stored, legacy

    def test_append_last_wins_and_tail_match_legacy(self):
        path = self.transcript("h1")
        agent = path.parent / "s1" / "subagents" / "agent-a.jsonl"
        agent.parent.mkdir(parents=True)
        path.write_text(line("m1", "r1", 1) + line("m2", "r2", 5))
        agent.write_text(line("a1", "q1", 3))
        read = lambda: (parse_transcript(path), load_subagents([agent.parent], 0, 2e9)[0])  # noqa: E731
        first, legacy = self.both_modes(read)
        self.assertEqual(first, legacy)
        with path.open("a") as fh:  # m1 updated (last wins), new m3 without final newline
            fh.write(line("m1", "r1", 7) + line("m3", "r3", 2, newline=False))
        with agent.open("a") as fh:
            fh.write(line("a1", "q1", 4))
        second, legacy = self.both_modes(read)
        self.assertEqual(second, legacy)
        self.assertEqual(second[0].usage.out, 7 + 5 + 2)
        self.assertEqual(second[1].usage.out, 4)

    def test_rows_carry_account_and_calibration_is_per_account(self):
        for home in ("h1", "h2"):
            self.transcript(home).write_text(line("m-" + home, "r", 1))
            parse_transcript(self.transcript(home))
        conn = runtime.connection()
        self.assertEqual([r[1] for r in claude_ingest.account_rows(conn, "v1")], ["m-h1"])
        self.assertEqual([r[1] for r in claude_ingest.account_rows(conn, "v2")], ["m-h2"])
        headers = {"v1": cal.empty() | {"usd_per_pct": 3}}
        runs = [SimpleNamespace(backend=b, usage=Usage(usd=12)) for b in ("claude-v1", "claude-v2")]
        snapshot = SimpleNamespace(sessions=[], iter_runs=lambda: runs)
        with patch.object(cal, "collect", return_value=cal.empty() | {"accounts": headers}):
            cal.enrich(snapshot, 1000)
        self.assertEqual(runs[0].usage.week_pct, 4)
        self.assertIsNone(runs[1].usage.week_pct)


if __name__ == "__main__":
    unittest.main()
