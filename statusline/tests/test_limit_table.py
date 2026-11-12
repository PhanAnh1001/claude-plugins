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

    def render(self, claude_home: Path | None = None, **extra: str) -> list[str]:
        payload = json.dumps({
            "workspace": {"current_dir": str(self.workdir)},
            "model": {"display_name": "Opus"},
            "rate_limits": {
                "five_hour": {"used_percentage": 5.3, "resets_at": self.now + 3600},
                "seven_day": {"used_percentage": 5, "resets_at": self.reset},
            },
        })
        env = clean_env(HOME=str(self.home), CLAUDE_HOME=str(claude_home or self.claude_home),
                        HYBRID_HANDS_STATE_DIR=str(self.state),
                        STATUSLINE_WEEK_SPLIT_SPAWN="0", STATUSLINE_GO_LIVE="0",
                        STATUSLINE_CLAUDE_V2="1",
                        **{"STATUSLINE_CODEX_DIR": str(self.home / "no-codex"), **extra})
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
        self.assertEqual(len(rows), 5, rows)
        self.assertTrue(rows[0].startswith("Claude v1 ultra"), rows)
        self.assertRegex(rows[1], r"^Claude v2 pro\s+5h:\?\s+\| 7d:\?$")
        self.assertEqual(rows[0].index("7d:"), rows[1].index("7d:"), rows)
        self.assertTrue(rows[2].startswith("· máy này"), rows)
        self.assertTrue(rows[3].startswith("· máy khác"), rows)
        self.assertTrue(rows[-1].startswith("Go"), rows)
        self.assert_aligned(rows)
        self.assertRegex(rows[0], r"7d:5% \(reset .+ · \$13\.74/1%\)")
        self.assertRegex(rows[2], r"7d:12\.2% \(T6 2\.1% · T7 5\.4%\)$")
        self.assertRegex(rows[3], r"7d:2\.8%$")

    def test_session_account_is_live_and_other_account_reads_its_own_cache(self) -> None:
        v2_home = self.home / ".claude-hand"
        v2_home.mkdir()
        cache = {"five": "7", "five_reset": str(self.now + 600), "week": "40",
                 "week_reset": str(self.now - 1)}
        (v2_home / ".statusline-cache.json").write_text(json.dumps(cache), encoding="utf-8")
        rows = self.table_rows(self.render())
        self.assertRegex(rows[0], r"^Claude v1 ultra\s+5h:5% ")
        self.assertRegex(rows[1], r"^Claude v2 pro\s+5h:~7% \(reset .+\)\s+\| 7d:\?$")
        # A v2 session: v2 is live (and cached under ~/.claude-hand), v1 comes from ~/.claude.
        rows = self.table_rows(self.render(claude_home=v2_home))
        self.assertRegex(rows[0], r"^Claude v1 ultra\s+5h:~5% \(reset .+\)\s+\| 7d:~5% ")
        self.assertRegex(rows[1], r"^Claude v2 pro\s+5h:5% ")
        self.assertEqual(json.loads((v2_home / ".statusline-cache.json").read_text())["five"], "5.3")

    def write_fable(self, percent: int, resets_at: int) -> None:
        reset = dt.datetime.fromtimestamp(resets_at, dt.timezone.utc).isoformat().replace("+00:00", ".5+00:00")
        fable = {"kind": "weekly_scoped", "group": "weekly", "percent": percent, "resets_at": reset,
                 "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None}}
        weekly = {"kind": "weekly_all", "percent": 51, "resets_at": reset, "scope": None}
        (self.home / ".claude.json").write_text(json.dumps({"cachedUsageUtilization": {
            "fetchedAtMs": self.now * 1000, "utilization": {"limits": [weekly, fable]}}}), encoding="utf-8")

    def test_fable_cell_ends_the_v1_row_from_the_cli_usage_cache(self) -> None:
        self.write_fable(6, self.reset)
        rows = self.table_rows(self.render())
        self.assertRegex(rows[0], r"\| 7d:5% \(reset .+\) \| Fable:~6% \(reset .+ · lấy .+\)$")
        self.assertRegex(rows[1], r"^Claude v2 pro\s+5h:\?\s+\| 7d:\?$")
        self.assert_aligned(rows)
        # Past its reset the cached % no longer applies; with no Fable limit there is no cell.
        self.write_fable(6, self.now - 60)
        self.assertRegex(self.table_rows(self.render())[0], r"\| Fable:\?$")
        (self.home / ".claude.json").write_text("{}", encoding="utf-8")
        self.assertNotIn("Fable", self.table_rows(self.render())[0])

    def test_gpt_row_reads_the_newest_codex_rollout_sample_and_today_cost(self) -> None:
        sessions = self.home / "codex" / "sessions" / "2026"
        sessions.mkdir(parents=True)
        prices = self.home / "prices.json"
        prices.write_text(json.dumps({"version": 1, "models": {
            "gpt-fixture": {"input": 2, "cached": 0.5, "output": 10}}}), encoding="utf-8")
        now = dt.datetime.now(dt.timezone.utc)

        def event(age: float, total: int, limits: dict) -> str:
            stamp = (now - dt.timedelta(seconds=age)).isoformat()
            usage = {"input_tokens": total, "cached_input_tokens": total // 2, "output_tokens": total // 10,
                     "total_tokens": total}
            return json.dumps({"timestamp": stamp, "type": "event_msg", "payload": {
                "type": "token_count", "info": {"total_token_usage": usage}, "rate_limits": limits}})

        week = {"primary": {"used_percent": 31, "window_minutes": 10080, "resets_at": self.now + 86400}}
        older = {"primary": {"used_percent": 90, "window_minutes": 300, "resets_at": self.now + 600}}
        lines = [json.dumps({"type": "session_meta", "payload": {"id": "t1"}}),
                 json.dumps({"type": "turn_context", "payload": {"model": "gpt-fixture"}}),
                 event(2, 1_000_000, older), event(1, 2_000_000, week), event(1, 2_000_000, week)]
        (sessions / "rollout-a.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rows = self.table_rows(self.render(STATUSLINE_CODEX_DIR=str(self.home / "codex"),
                                           HYBRID_HANDS_PRICING_FILE=str(prices)))
        # 2M input (1M cached) + 0.2M output: 1x2 + 1x0.5 + 0.2x10 = 4.50; the duplicate counts once.
        self.assertRegex(rows[-1], r"^GPT\s+5h:\?\s+\| 7d:31% \(reset .+\)\s+\| hôm nay ~\$4\.50$")

    def test_missing_go_keeps_the_other_rows_aligned(self) -> None:
        self.write_summary()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 4, rows)
        self.assertFalse(any(row.startswith("Go") for row in rows), rows)
        self.assert_aligned(rows)

    def test_missing_summary_keeps_claude_and_go_aligned(self) -> None:
        self.write_go_live()
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 3, rows)
        self.assertFalse(any("máy" in row for row in rows), rows)
        self.assertNotIn("$", rows[0])
        self.assert_aligned(rows)

    def test_only_claude_prints_a_single_row_table(self) -> None:
        rows = self.table_rows(self.render())
        self.assertEqual(len(rows), 2, rows)
        self.assert_aligned(rows)
        self.assertRegex(rows[0], r"^Claude v1 ultra\s+5h:5% \(reset .+\) \| 7d:5% \(reset .+\)$")


if __name__ == "__main__":
    unittest.main()
