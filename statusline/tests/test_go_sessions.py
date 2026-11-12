"""Tests for scripts/go_sessions.py: Go week runs; the summary no longer carries groups."""
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
                  "cwd": str(self.repo), "model": gs.LEGACY_GO_MODEL, "tokens": tokens or {}}
        (self.state / gs.RUNS_SUBDIR / f"{run_id}.json").write_text(json.dumps(record))

    def finished(self, run_id: str, parent: str | None, usd: float, ended: float) -> None:
        self.run_record(run_id, parent)
        self.log.append(json.dumps({"run_id": run_id, "ended": iso(ended), "cost_usd": usd}))
        (self.state / gs.GO_USAGE_LOG_NAME).write_text("\n".join(self.log) + "\n")

    def usd_by_parent(self) -> dict:
        week = gs.load_go_week(self.home, self.state)
        self.assertEqual((week.window_start, week.limit_usd), (WINDOW_START, LIMIT))
        totals: dict = {}
        for run in week.runs:
            totals[run.parent] = round(totals.get(run.parent, 0.0) + run.usd, 4)
        return totals

    def test_finished_and_running_runs_in_the_window(self) -> None:
        self.finished("r1", "A", 1.0, NOW - 3600)
        self.finished("old", "A", 5.0, WINDOW_START - 60)
        self.finished("r2", None, 2.0, NOW - 3600)
        # 1M uncached input + 1M output at the default price = 0.30 + 1.20 USD.
        self.run_record("r3", "B", status=gs.RUN_STATUS_RUNNING,
                        tokens={"input": 1_000_000, "cached_input": 0, "output": 1_000_000})
        self.assertEqual(self.usd_by_parent(), {"A": 1.0, None: 2.0, "B": 1.5})

    def test_logged_run_still_marked_running_is_not_counted_twice(self) -> None:
        self.finished("r1", "A", 1.0, NOW - 3600)
        self.run_record("r1", "A", status=gs.RUN_STATUS_RUNNING, tokens={"output": 10_000_000})
        self.assertEqual(self.usd_by_parent(), {"A": 1.0})

    def test_summary_has_no_groups_and_missing_limit_or_window_drops_go(self) -> None:
        week = gs.load_go_week(self.home, self.state)
        ledger = {"messages": {"m1": [NOW - 60, 24.0, "A"]},
                  "sessions": {"A": {"cwd": str(self.repo), "last_ts": NOW, "custom_title": "old"}},
                  "unpriced": {}}
        summary = ws.build_summary([ws.Sample(NOW - 10, 4, CLAUDE_RESET)], ledger, NOW, [], week)
        self.assertFalse({"groups", "go_week"} & set(summary))
        self.assertEqual(summary["sessions"]["A"]["pct"], 2.0)
        self.write_limit(None)
        self.assertIsNone(gs.load_go_week(self.home, self.state))
        self.write_limit(LIMIT)
        (self.home / gs.GO_LIVE_CACHE_NAME).unlink()
        self.assertIsNone(gs.load_go_week(self.home, self.state))

    def test_estimate_cost_matches_hybrid_hands_formula(self) -> None:
        tokens = {"input": 4_589_145, "cached_input": 4_481_152, "output": 32_152}
        self.assertAlmostEqual(gs.estimate_cost(tokens), 0.097867, places=5)
        self.assertIsNone(gs.estimate_cost(tokens, "deepseek-unknown"))


if __name__ == "__main__":
    unittest.main()
