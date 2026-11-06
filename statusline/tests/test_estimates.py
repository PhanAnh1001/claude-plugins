"""Tests for the 7-day estimate in week_split.py and the session names in usage_ledger.py."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import usage_ledger as ul  # noqa: E402
import week_split as ws  # noqa: E402

NOW = 1_794_000_000.0
RESET = NOW + 3 * 86400
CALIB = ws.Rate(10.0, ws.RATE_CALIB, 1)


def index_of(rows: list[tuple[float, float]]) -> ws.UsdIndex:
    return ws.UsdIndex({f"m{i}": [ts, usd, "s"] for i, (ts, usd) in enumerate(rows)})


class SampleColumnsTest(unittest.TestCase):
    def test_three_columns(self) -> None:
        self.assertEqual(ws.parse_sample("10\t4\t99\n"), ws.Sample(10, 4, 99))

    def test_extra_columns_ignored(self) -> None:
        self.assertEqual(ws.parse_sample("10\t4\t99\t12\t50\n"), ws.Sample(10, 4, 99))

    def test_short_or_broken_lines_dropped(self) -> None:
        self.assertIsNone(ws.parse_sample("10\t4\n"))
        self.assertIsNone(ws.parse_sample("10\tx\t99\n"))

    def test_rewrite_keeps_three_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ws.SAMPLES_NAME
            old = NOW - ws.RETENTION_SECONDS - 10
            path.write_text(f"{old:.0f}\t1\t{RESET:.0f}\n{NOW:.0f}\t4\t{RESET:.0f}\t9\t1\n")
            ws.load_samples(path, NOW)
            self.assertEqual(path.read_text(), f"{NOW:.0f}\t4\t{RESET:.0f}\n")


class EstimateWeekTest(unittest.TestCase):
    def test_counts_usd_since_the_value_last_changed(self) -> None:
        samples = [ws.Sample(NOW - 3000, 3, RESET), ws.Sample(NOW - 2000, 4, RESET),
                   ws.Sample(NOW - 1000, 4, RESET)]
        index = index_of([(NOW - 2500, 50.0), (NOW - 1500, 3.0)])  # only the second counts
        estimate = ws.estimate_week(samples, index, NOW, CALIB)
        self.assertEqual(estimate, {"pct": 4.3, "base": 4, "reset": int(RESET), "label": "calib"})

    def test_capped_at_p_plus_point_nine(self) -> None:
        samples = [ws.Sample(NOW - 1000, 4, RESET)]
        estimate = ws.estimate_week(samples, index_of([(NOW - 500, 500.0)]), NOW, CALIB)
        self.assertEqual(estimate["pct"], 4.9)

    def test_reset_change_starts_a_new_run(self) -> None:
        samples = [ws.Sample(NOW - 3000, 4, RESET - 86400 * 7),
                   ws.Sample(NOW - 1000, 4, RESET)]
        estimate = ws.estimate_week(samples, index_of([(NOW - 2000, 5.0)]), NOW, CALIB)
        self.assertEqual(estimate["pct"], 4.0)

    def test_prior_label_in_summary(self) -> None:
        ledger = {"messages": {"a": [NOW - 60, 1.2, "s"]}, "sessions": {}, "unpriced": {}}
        summary = ws.build_summary([ws.Sample(NOW - 100, 4, RESET)], ledger, NOW, [])
        week = summary["claude_estimates"]["week"]
        self.assertEqual((week["pct"], week["label"]), (4.1, ws.RATE_PRIOR))
        self.assertNotIn("five", summary["claude_estimates"])
        self.assertNotIn("go_week", summary)


class LedgerTitleTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        (self.home / "projects" / "p" / "s1" / "subagents").mkdir(parents=True)
        self.main = self.home / "projects" / "p" / "s1.jsonl"

    def usage(self, msg_id: str) -> str:
        return json.dumps({"type": "assistant", "requestId": f"r{msg_id}",
                           "timestamp": "2026-11-06T08:00:00Z",
                           "message": {"id": msg_id, "model": "claude-opus-5-5",
                                       "usage": {"output_tokens": 1}}}, separators=(",", ":"))

    def title(self, kind: str, key: str, value: str) -> str:
        return json.dumps({"type": kind, key: value, "sessionId": "s1"}, separators=(",", ":"))

    def ledger(self) -> dict:
        return ul.update_ledger(self.home, 1_794_000_000.0)

    def test_titles_recorded_later_wins(self) -> None:
        self.main.write_text("\n".join([
            self.usage("a"), self.title("custom-title", "customTitle", "old"),
            self.title("agent-name", "agentName", "agent"),
            self.title("custom-title", "customTitle", "luxian"),
            self.title("ai-title", "aiTitle", "Sửa statusline"), ""]))
        session = self.ledger()["sessions"]["s1"]
        self.assertEqual((session["custom_title"], session["agent_name"]), ("luxian", "agent"))
        self.assertEqual(ul.session_name(session), ("luxian", "Sửa statusline"))

    def test_agent_name_when_no_custom_title(self) -> None:
        self.main.write_text("\n".join([self.usage("a"),
                                        self.title("agent-name", "agentName", "hand-1"), ""]))
        self.assertEqual(ul.session_name(self.ledger()["sessions"]["s1"]), ("hand-1", ""))

    def test_subagent_titles_ignored(self) -> None:
        self.main.write_text(self.usage("a") + "\n")
        sub = self.home / "projects" / "p" / "s1" / "subagents" / "agent-1.jsonl"
        sub.write_text(self.title("custom-title", "customTitle", "sub") + "\n")
        self.assertNotIn("custom_title", self.ledger()["sessions"]["s1"])


if __name__ == "__main__":
    unittest.main()
