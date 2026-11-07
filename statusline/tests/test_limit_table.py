"""Tests for the aligned limit table of statusline.sh (Claude / này / khác / Go / GPT rows)."""
from __future__ import annotations

import datetime as dt
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

    def test_gpt_row_uses_latest_quota_sample_and_today_cost(self) -> None:
        self.state.mkdir()
        ledger = self.state / "codex_usage.jsonl"
        now = dt.datetime.now(dt.timezone.utc)
        start = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        span = now - start
        local_offset = start.utcoffset() or dt.timedelta(0)
        tz = dt.timezone(-local_offset if local_offset else dt.timedelta(hours=5))

        def iso(moment: dt.datetime) -> str:
            return moment.astimezone(tz).isoformat()

        def at(ratio: float) -> dt.datetime:
            return start + span * ratio

        def rec(ended: dt.datetime, cost: object, windows: object, **extra: object) -> dict:
            return {"schema": 1, "ended": iso(ended), "codex_home": ".codex-hand",
                    "cost_usd": cost, "windows": windows, **extra}

        def window(percent: object, reset: dt.datetime) -> dict:
            return {"used_percent": percent, "resets_at": iso(reset)}

        # Phase 1: latest by ended (not line order), today's cost only, bad lines skipped.
        latest = rec(at(0.95), 1.0, {"5h": window(42.4, now + dt.timedelta(hours=2)),
                                     "7d": window(67.6, now + dt.timedelta(days=3))})
        lines = [
            json.dumps(latest), "{broken", json.dumps(42),
            json.dumps(rec(at(0.2), 0.25, {"5h": window(10, now + dt.timedelta(hours=1))})),
            json.dumps(rec(at(0.7), 0.1, {"5h": {"used_percent": "nope"}})),
            json.dumps(rec(at(0.5), 0.5,
                           {"5h": None, "7d": window(20, now + dt.timedelta(days=1))})),
            json.dumps(rec(start - dt.timedelta(hours=2), 99,
                           {"5h": window(90, now + dt.timedelta(hours=1))})),
            json.dumps(rec(now + dt.timedelta(hours=1), 50,
                           {"5h": window(30, now + dt.timedelta(hours=1))})),
            json.dumps(rec(now, 77, {"5h": window(30, now + dt.timedelta(hours=1))},
                           codex_home=".codex")),
            json.dumps({"schema": 2, "ended": iso(at(0.3)), "codex_home": ".codex-hand",
                        "cost_usd": 5, "windows": {}}),
            json.dumps({"schema": 1, "ended": "not-a-date", "codex_home": ".codex-hand",
                        "cost_usd": 5, "windows": {}}),
            json.dumps({"schema": 1, "codex_home": ".codex-hand", "cost_usd": 5, "windows": {}}),
        ]
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.write_go_live()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 3, rows)
        self.assertTrue(rows[1].startswith("Go"), rows)
        self.assertTrue(rows[2].startswith("GPT"), rows)
        self.assert_aligned(rows)
        self.assertRegex(rows[2], r"^GPT\s+5h:42%\s+\| 7d:68%\s+\| hôm nay ~\$1\.85$")

        # Phase 2: expired 5h reset drops that % only; the older sample must not fill it in.
        expired = rec(at(0.95), 1.0, {"5h": window(42.4, now - dt.timedelta(minutes=1)),
                                      "7d": window(67.6, now + dt.timedelta(days=3))})
        older = rec(at(0.2), 0.25, {"5h": window(10, now + dt.timedelta(hours=1))})
        ledger.write_text(json.dumps(expired) + "\n" + json.dumps(older) + "\n", encoding="utf-8")
        rows = self.table_rows(self.render())
        self.assertTrue(rows[-1].startswith("GPT"), rows)
        self.assertRegex(rows[-1], r"^GPT\s+5h:--\s+\| 7d:68%\s+\| hôm nay ~\$1\.25$")

        # Phase 3: only a sample older than 24h, then no ledger at all: no GPT row, exit 0.
        old = rec(now - dt.timedelta(hours=25), 3.0,
                  {"5h": window(42.4, now + dt.timedelta(hours=1))})
        ledger.write_text(json.dumps(old) + "\n", encoding="utf-8")
        rows = self.table_rows(self.render())
        self.assertFalse(any(row.startswith("GPT") for row in rows), rows)
        ledger.unlink()
        rows = self.table_rows(self.render())
        self.assertFalse(any(row.startswith("GPT") for row in rows), rows)

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
