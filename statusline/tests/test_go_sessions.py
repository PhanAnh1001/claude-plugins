"""Tests for scripts/go_sessions.py: Go week runs and the main-session groups in the summary."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import go_sessions as gs  # noqa: E402
import week_split as ws  # noqa: E402

NOW = 1_794_000_000.0
GO_RESET = NOW + 2 * 86400
WINDOW_START = GO_RESET - gs.GO_WEEK_SECONDS
CLAUDE_RESET = NOW + 3 * 86400
LIMIT = 50.0
MODEL = "deepseek-v4.1-flash"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


class GoSessionsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.home, self.state = root / "claude", root / "hh"
        (self.state / gs.RUNS_SUBDIR).mkdir(parents=True)
        self.home.mkdir()
        self.repo = root / "repo"
        side = self.repo / ws.DEFAULT_SIDE_STATE_DIR
        side.mkdir(parents=True)
        (self.repo / ".git").mkdir()
        for name, child, parent in (("b", "B", "A"), ("c", "C", "B")):
            (side / f"{name}.json").write_text(json.dumps(
                {"uuid": child, "provider": "claude", "parent_session": parent}))
        self.write_cache(GO_RESET)
        self.write_limit(LIMIT)
        self.log: list[str] = []

    def write_cache(self, reset: float) -> None:
        (self.home / gs.GO_LIVE_CACHE_NAME).write_text(json.dumps(
            {"state": "ok", "windows": {"weekly": {"percent": 3, "resets_at": int(reset)}}}))

    def write_limit(self, limit: float | None) -> None:
        week = {"percent": 1.0} if limit is None else {"percent": 1.0, "limit_usd": limit}
        (self.state / gs.GO_SUMMARY_NAME).write_text(json.dumps({"models": {MODEL: {"7d": week}}}))

    def run_record(self, run_id: str, parent: str | None, status: str = "done",
                   tokens: dict | None = None) -> None:
        record = {"run_id": run_id, "parent_session": parent, "status": status,
                  "cwd": str(self.repo), "tokens": tokens or {}}
        (self.state / gs.RUNS_SUBDIR / f"{run_id}.json").write_text(json.dumps(record))

    def finished(self, run_id: str, parent: str | None, usd: float, ended: float) -> None:
        self.run_record(run_id, parent)
        self.log.append(json.dumps({"run_id": run_id, "ended": iso(ended), "cost_usd": usd}))
        (self.state / gs.GO_USAGE_LOG_NAME).write_text("\n".join(self.log) + "\n")

    def summary(self) -> dict:
        week = gs.load_go_week(self.home, self.state)
        ledger = {"messages": {"m1": [NOW - 60, 24.0, "A"], "m2": [NOW - 60, 12.0, "X"]},
                  "sessions": {"A": {"cwd": str(self.repo), "last_ts": NOW, "custom_title": "main"},
                               "X": {"cwd": "", "last_ts": NOW}}, "unpriced": {}}
        return ws.build_summary([ws.Sample(NOW - 10, 4, CLAUDE_RESET)], ledger, NOW, [], week)

    def groups(self) -> dict[str, dict]:
        return {group["root"]: group for group in self.summary()["groups"]}

    def test_finished_and_running_runs_roll_up_nested_side_sessions(self) -> None:
        self.finished("r1", "A", 1.0, NOW - 3600)
        self.finished("r2", "C", 2.0, NOW - 3600)
        # 1M uncached input + 1M output at the default price = 0.30 + 1.20 USD.
        self.run_record("r3", "B", status=gs.RUN_STATUS_RUNNING,
                        tokens={"input": 1_000_000, "cached_input": 0, "output": 1_000_000})
        groups = self.groups()
        self.assertEqual(set(groups), {"A", "X"})
        self.assertEqual(groups["A"]["members"], ["A", "B", "C"])
        self.assertEqual((groups["A"]["go_usd"], groups["A"]["go_pct"]), (4.5, 9.0))
        self.assertEqual((groups["A"]["claude_pct"], groups["A"]["name"]), (2.0, "main"))
        self.assertEqual(groups["X"]["go_pct"], 0.0)
        self.assertEqual([g["root"] for g in self.summary()["groups"]], ["A", "X"])
        self.assertEqual(self.summary()["go_week"],
                         {"window_start": int(WINDOW_START), "limit_usd": LIMIT})

    def test_logged_run_still_marked_running_is_not_counted_twice(self) -> None:
        self.finished("r1", "A", 1.0, NOW - 3600)
        self.run_record("r1", "A", status=gs.RUN_STATUS_RUNNING, tokens={"output": 10_000_000})
        self.assertEqual(self.groups()["A"]["go_usd"], 1.0)

    def test_run_without_parent_belongs_to_no_session(self) -> None:
        self.finished("r1", None, 5.0, NOW - 3600)
        self.assertEqual(self.groups()["A"]["go_usd"], 0.0)

    def test_run_before_the_window_is_dropped(self) -> None:
        self.finished("old", "A", 5.0, WINDOW_START - 60)
        self.finished("new", "A", 1.0, WINDOW_START + 60)
        self.assertEqual(self.groups()["A"]["go_usd"], 1.0)

    def test_missing_limit_or_window_drops_go(self) -> None:
        self.finished("r1", "A", 1.0, NOW - 3600)
        self.write_limit(None)
        summary = self.summary()
        self.assertNotIn("go_week", summary)
        self.assertIsNone({g["root"]: g for g in summary["groups"]}["A"]["go_pct"])
        self.write_limit(LIMIT)
        (self.home / gs.GO_LIVE_CACHE_NAME).unlink()
        self.assertIsNone(gs.load_go_week(self.home, self.state))

    def test_estimate_cost_matches_hybrid_hands_formula(self) -> None:
        tokens = {"input": 4_589_145, "cached_input": 4_481_152, "output": 32_152}
        self.assertAlmostEqual(gs.estimate_cost(tokens), 0.097867, places=5)


if __name__ == "__main__":
    unittest.main()
