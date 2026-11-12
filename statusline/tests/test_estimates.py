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
        self.assertFalse({"go_week", "groups"} & set(summary))


if __name__ == "__main__":
    unittest.main()
