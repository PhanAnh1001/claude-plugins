"""A synthetic unfinished Claude transcript keeps elapsed time advancing."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hh_ps.models import Session, Snapshot
from hh_ps.render import render_json, render_text
from hh_ps.transcript_source import load_subagents
from hh_store import runtime as store_runtime
from unittest.mock import patch


class RunningUsageTest(unittest.TestCase):
    def setUp(self):
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        env = patch.dict("os.environ", {"HYBRID_HANDS_STATE_DIR": state.name})
        env.start()
        store_runtime._reset_for_tests()
        self.addCleanup(store_runtime._reset_for_tests)
        self.addCleanup(env.stop)

    def test_unfinished_claude_duration_advances(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "agent-fake.jsonl").write_text(json.dumps({
                "type": "assistant", "timestamp": "2026-11-07T00:00:00Z",
                "agentType": "general-purpose", "effort": "high",
                "message": {"model": "claude-opus-5-5", "usage": {
                    "input_tokens": 10, "output_tokens": 2}},
            }) + "\n")
            snapshots = []
            for now in (1794009660.0, 1794009670.0):
                session = Session("fake", "fake", "busy", temporary, None,
                                  now - 60, now, False, True)
                session.subagents = load_subagents([folder], now - 3600, now)
                snapshots.append(Snapshot([session], [], 3600, temporary,
                                          False, None, now))
            rows = [render_json(s)["sessions"][0]["subagents"][0] for s in snapshots]
            self.assertEqual(rows[1]["duration_seconds"] - rows[0]["duration_seconds"], 10)
            self.assertIsNone(rows[1]["ended_at"])
            text = render_text(snapshots[1])
            self.assertIn("đang chạy", next(line for line in text.splitlines()
                                            if "claude-opus-5-5/high" in line))
            self.assertIn("claude-opus-5-5/high", text)
