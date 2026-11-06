"""Tests for the aligned limit table of statusline.sh (Claude / này / khác / Go rows)."""
from __future__ import annotations

import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

STATUSLINE = SCRIPTS_DIR / "statusline.sh"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
SUMMARY = ".statusline-week-split.json"
GO_CACHE = ".statusline-go-usage.json"
DAYS = [{"wd": "T6", "pct": 2.14}, {"wd": "T7", "pct": 5.4}]
USD_PER_PCT = 13.74


class LimitTableTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()
        self.state = self.home / "go-state"
        self.workdir = self.home / "project"
        self.workdir.mkdir()
        self.now = int(time.time())
        self.reset = self.now + 3 * 86400

    def write_summary(self) -> None:
        (self.claude_home / SUMMARY).write_text(json.dumps({
            "version": 2, "computed_at": self.now, "reset": self.reset,
            "window_start": self.reset - 604800, "total": 15, "local": 12.2, "other": 2.8,
            "local_usd": 167.6, "usd_per_pct": USD_PER_PCT, "rate_label": "calib",
            "calib_n": 3, "days": DAYS, "sessions": {}, "unpriced_models": [],
        }), encoding="utf-8")

    def write_go_live(self) -> None:
        (self.claude_home / GO_CACHE).write_text(json.dumps({
            "fetched_at": self.now, "last_ok_at": self.now, "state": "ok", "windows": {
                "rolling": {"percent": 5.8, "status": "ok", "resets_at": self.now + 3600},
                "weekly": {"percent": 13.4, "status": "ok",
                           "resets_at": self.now + 2 * 86400},
                "monthly": {"percent": 6.4, "status": "ok",
                            "resets_at": self.now + 20 * 86400},
            },
        }), encoding="utf-8")

    def render(self) -> list[str]:
        payload = json.dumps({
            "workspace": {"current_dir": str(self.workdir)},
            "model": {"display_name": "Opus"},
            "rate_limits": {
                "five_hour": {"used_percentage": 5.3, "resets_at": self.now + 3600},
                "seven_day": {"used_percentage": 5, "resets_at": self.reset},
            },
        })
        env = clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home),
                        HYBRID_HANDS_STATE_DIR=str(self.state),
                        STATUSLINE_WEEK_SPLIT_SPAWN="0", STATUSLINE_GO_LIVE="0")
        result = run_bash(STATUSLINE, [], env, stdin=payload, cwd=self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        return ANSI_ESCAPE.sub("", result.stdout).split("\n")

    def table_rows(self, lines: list[str]) -> list[str]:
        return lines[2:]

    def assert_aligned(self, rows: list[str]) -> None:
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(row.startswith((" ", "\t")), f"row starts with whitespace: {row!r}")
        positions = {row.index("|") for row in rows}
        self.assertEqual(len(positions), 1, rows)

    def test_four_rows_align_and_usd_sits_in_the_claude_parens(self) -> None:
        self.write_summary()
        self.write_go_live()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 4, rows)
        self.assertTrue(rows[0].startswith("Claude"), rows)
        self.assertTrue(rows[1].startswith("· máy này"), rows)
        self.assertTrue(rows[2].startswith("· máy khác"), rows)
        self.assertTrue(rows[3].startswith("Go"), rows)
        self.assert_aligned(rows)
        self.assertRegex(rows[0], r"7d:5% \(reset .+ · \$13\.74/1%\)")
        self.assertRegex(rows[1], r"7d:12\.2% \(T6 2\.1% · T7 5\.4%\)$")
        self.assertRegex(rows[2], r"7d:2\.8%$")

    def test_missing_go_keeps_the_other_rows_aligned(self) -> None:
        self.write_summary()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 3, rows)
        self.assertFalse(any(row.startswith("Go") for row in rows), rows)
        self.assert_aligned(rows)

    def test_missing_summary_keeps_claude_and_go_aligned(self) -> None:
        self.write_go_live()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 2, rows)
        self.assertFalse(any("máy" in row for row in rows), rows)
        self.assertNotIn("$", rows[0])
        self.assert_aligned(rows)

    def test_only_claude_prints_a_single_row_table(self) -> None:
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 1, rows)
        self.assert_aligned(rows)
        self.assertRegex(rows[0], r"^Claude\s+5h:5% \(reset .+\) \| 7d:5% \(reset .+\)$")


if __name__ == "__main__":
    unittest.main()
