"""Tests for scripts/week-split.sh and its line inside statusline.sh."""
from __future__ import annotations

import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

WEEK_SPLIT = SCRIPTS_DIR / "week-split.sh"
STATUSLINE = SCRIPTS_DIR / "statusline.sh"
SAMPLES = ".statusline-week-samples.tsv"
SUMMARY = ".statusline-week-split.json"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
RESET_EPOCH = 1794549600
DAYS = [{"wd": "T6", "pct": 2.14}, {"wd": "T7", "pct": 5.4}, {"wd": "CN", "pct": 0}]
SID = "abcdef12-3456"
SESSIONS = {SID: {"usd": 1.0, "total_usd": 11.0, "pct": 0.8}}
NAME = "luxian-statusline"
EXPECTED = "7d:12.2% (T6 2.1% · T7 5.4% · CN 0.0%)\x1f7d:2.8%\x1f$13.74/1%"
GO_MODEL = "deepseek-v4.1-flash"


class WeekSplitShellTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()

    def env(self, **extra: str) -> dict[str, str]:
        return clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home), **extra)

    def write_summary(self, calibrated: bool = True, reset: int = RESET_EPOCH,
                      computed_at: int | None = None, days: list | None = None,
                      version: int = 2) -> None:
        document = {
            "version": version,
            "computed_at": int(time.time()) if computed_at is None else computed_at,
            "reset": reset, "window_start": reset - 604800, "total": 15, "local": 12.2,
            "other": 2.8, "local_usd": 167.6, "usd_per_pct": 13.74,
            "rate_label": "calib" if calibrated else "prior", "calib_n": 3,
            "days": DAYS if days is None else days, "sessions": SESSIONS, "unpriced_models": [],
        }
        (self.claude_home / SUMMARY).write_text(json.dumps(document), encoding="utf-8")

    def run_split(self, *args: str, env: dict[str, str] | None = None) -> str:
        result = run_bash(WEEK_SPLIT, list(args), env or self.env())
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def sample_lines(self) -> list[str]:
        path = self.claude_home / SAMPLES
        return path.read_text().splitlines() if path.exists() else []

    def test_samples_not_duplicated(self) -> None:
        self.run_split("15", str(RESET_EPOCH), "", SID, NAME)
        self.run_split("15", str(RESET_EPOCH), "", SID, NAME)
        self.assertEqual(len(self.sample_lines()), 1)
        self.run_split("16", str(RESET_EPOCH), "")
        lines = self.sample_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[-1].split("\t")[1:], ["16", str(RESET_EPOCH)])

    def test_old_identical_sample_is_repeated(self) -> None:
        old = int(time.time()) - 400
        (self.claude_home / SAMPLES).write_text(f"{old}\t15\t{RESET_EPOCH}\n")
        self.run_split("15", str(RESET_EPOCH), "", SID, NAME)
        self.assertEqual(len(self.sample_lines()), 2)

    def test_no_sample_without_live_values(self) -> None:
        self.run_split("", "", str(RESET_EPOCH))
        self.assertEqual(self.sample_lines(), [])

    def test_line_format_plain_and_colored(self) -> None:
        self.write_summary()
        self.assertEqual(self.run_split("15", str(RESET_EPOCH), "", SID, NAME), EXPECTED + "\n")
        colored = self.run_split("--color", "15", str(RESET_EPOCH), "", SID, NAME)
        self.assertIn("\x1b[32m", colored)
        self.assertEqual(ANSI_ESCAPE.sub("", colored), EXPECTED + "\n")

    def test_tilde_when_not_calibrated_or_stale(self) -> None:
        expected = ("7d:~12.2% (T6 2.1% · T7 5.4% · CN 0.0%)\x1f7d:~2.8%"
                    "\x1f~$13.74/1%\n")
        self.write_summary(calibrated=False)
        self.assertEqual(self.run_split("15", str(RESET_EPOCH), "", SID, NAME), expected)
        self.write_summary(computed_at=int(time.time()) - 2000)
        self.assertEqual(self.run_split("15", str(RESET_EPOCH), "", SID, NAME), expected)

    def test_empty_days_drop_parentheses(self) -> None:
        self.write_summary(days=[])
        self.assertEqual(self.run_split("", "", str(RESET_EPOCH)),
                         "7d:12.2%\x1f7d:2.8%\x1f$13.74/1%\n")

    def test_session_arguments_no_longer_print_a_session_part(self) -> None:
        self.write_summary(days=[])
        self.assertEqual(self.run_split("", "", str(RESET_EPOCH), SID, NAME),
                         "7d:12.2%\x1f7d:2.8%\x1f$13.74/1%\n")

    def test_version_1_summary_not_printed(self) -> None:
        self.write_summary(version=1)
        self.assertEqual(self.run_split("15", str(RESET_EPOCH), "", SID, NAME), "")

    def test_no_line_when_reset_differs(self) -> None:
        self.write_summary(reset=RESET_EPOCH - 7200)
        self.assertEqual(self.run_split("15", str(RESET_EPOCH), "", SID, NAME), "")
        self.write_summary()
        self.assertEqual(self.run_split("", "", ""), "")

    def test_disabled_does_nothing(self) -> None:
        self.write_summary()
        out = self.run_split("15", str(RESET_EPOCH), "", env=self.env(STATUSLINE_WEEK_SPLIT="0"))
        self.assertEqual(out, "")
        self.assertEqual(self.sample_lines(), [])

    def test_spawn_writes_summary_in_background(self) -> None:
        self.run_split("15", str(RESET_EPOCH), "", env=self.env(STATUSLINE_WEEK_SPLIT_SPAWN="1"))
        summary = self.claude_home / SUMMARY
        for _ in range(50):
            if summary.exists():
                break
            time.sleep(0.1)
        self.assertEqual(json.loads(summary.read_text())["total"], 15)

    def test_statusline_places_line_after_claude_and_before_go(self) -> None:
        state = self.home / "go-state"
        state.mkdir()
        (state / "go_usage_summary.json").write_text(json.dumps({
            "updated_at": int(time.time()),
            "models": {GO_MODEL: {"5h": {"percent": 1, "estimated": False},
                                  "7d": {"percent": 2, "estimated": False}}},
        }))
        self.write_summary()
        payload = json.dumps({
            "workspace": {"current_dir": str(self.home)}, "model": {"display_name": "Opus"},
            "session_id": SID, "session_name": NAME,
            "rate_limits": {
                "five_hour": {"used_percentage": 5, "resets_at": RESET_EPOCH},
                "seven_day": {"used_percentage": 15, "resets_at": RESET_EPOCH}},
        })
        env = clean_env(HOME=str(self.home), HYBRID_HANDS_STATE_DIR=str(state))
        result = run_bash(STATUSLINE, [], env, stdin=payload, cwd=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = ANSI_ESCAPE.sub("", result.stdout).split("\n")
        self.assertRegex(lines[2],
                         r"^Claude\s+5h:5% \(reset .+\) \| 7d:15% \(reset .+ · \$13\.74/1%\)$")
        self.assertRegex(lines[3], r"^· máy này\s+\| 7d:12\.2% \(T6 2\.1% · T7 5\.4% · CN 0\.0%\)$")
        self.assertRegex(lines[4], r"^· máy khác\s+\| 7d:2\.8%$")
        self.assertRegex(lines[5], r"^Go\s+DS 5h 1\.0%\s+\| tuần 2\.0%$")
        self.assertEqual({line.index("|") for line in lines[2:6]},
                         {len(lines[2].split("|")[0])})


if __name__ == "__main__":
    unittest.main()
