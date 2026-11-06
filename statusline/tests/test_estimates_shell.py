"""Tests for the decimal estimates on line 3 (Claude 7d) and on the Go line of statusline.sh."""
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
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"
WEEK_RESET = 1794549600
GO_MODEL = "deepseek-v4.1-flash"
GO_STALE_SECONDS = 5 * 3600
ESTIMATE_FRESH_SECONDS = 1800


class EstimateShellTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()
        self.state = self.home / "go-state"
        self.state.mkdir()

    def write_summary(self, pct: float = 4.3, base: float = 4, reset: int = WEEK_RESET,
                      age: int = 0) -> None:
        (self.claude_home / ".statusline-week-split.json").write_text(json.dumps({
            "version": 2, "computed_at": int(time.time()) - age, "reset": reset,
            "claude_estimates": {"week": {"pct": pct, "base": base, "reset": reset,
                                          "label": "calib"}}}))

    def write_go(self, rolling: float, weekly: float, monthly: float, est: tuple,
                 rolling_reset_in: int = 3600, age: int = 0) -> None:
        now = int(time.time())
        windows = {"rolling": {"percent": rolling, "status": "ok",
                               "resets_at": now + rolling_reset_in},
                   "weekly": {"percent": weekly, "status": "ok", "resets_at": now + 86400},
                   "monthly": {"percent": monthly, "status": "ok", "resets_at": now + 9 * 86400}}
        (self.claude_home / ".statusline-go-usage.json").write_text(json.dumps(
            {"fetched_at": now, "last_ok_at": now, "state": "ok", "windows": windows}))
        models = {GO_MODEL: {key: {"percent": value, "estimated": True}
                             for key, value in zip(("5h", "7d", "30d"), est)}}
        (self.state / "go_usage_summary.json").write_text(json.dumps(
            {"updated_at": now - age, "models": models}))

    def render(self, week: float | None = 4, five: float | None = None) -> list[str]:
        limits = {}
        if week is not None:
            limits["seven_day"] = {"used_percentage": week, "resets_at": WEEK_RESET}
        if five is not None:
            limits["five_hour"] = {"used_percentage": five, "resets_at": WEEK_RESET}
        payload = {"workspace": {"current_dir": str(self.home)}, "model": {"display_name": "O"}}
        if limits:
            payload["rate_limits"] = limits
        env = clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home),
                        HYBRID_HANDS_STATE_DIR=str(self.state), STATUSLINE_GO_LIVE="0")
        result = run_bash(STATUSLINE, [], env, stdin=json.dumps(payload), cwd=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split("\n")

    def line3(self, **kwargs) -> str:
        return ANSI_ESCAPE.sub("", self.render(**kwargs)[2])

    # --- Claude 7d ---
    def test_estimate_shown_with_one_decimal_and_integer_colour(self) -> None:
        self.write_summary()
        lines = self.render()
        self.assertRegex(ANSI_ESCAPE.sub("", lines[2]), r"^Claude\s+5h:- \| 7d:~4\.3% \(reset .+\)$")
        self.assertIn(f"{GREEN}4.3%{RESET}", lines[2])

    def test_base_mismatch_prints_integer(self) -> None:
        self.write_summary(base=3)
        self.assertRegex(self.line3(), r"7d:4% \(reset")

    def test_reset_far_away_prints_integer(self) -> None:
        self.write_summary(reset=WEEK_RESET - 7200)
        self.assertRegex(self.line3(), r"7d:4% \(reset")

    def test_old_summary_prints_integer(self) -> None:
        self.write_summary(age=ESTIMATE_FRESH_SECONDS + 60)
        self.assertRegex(self.line3(), r"7d:4% \(reset")

    def test_cached_value_with_estimate_has_one_tilde(self) -> None:
        self.render()  # fills the cache
        self.write_summary()
        self.assertRegex(self.line3(week=None), r"^Claude\s+5h:- \| 7d:~4\.3% \(reset .+\)$")

    def test_live_five_still_printed(self) -> None:
        self.assertRegex(self.line3(five=12.3), r"^Claude\s+5h:12% \(reset .+\) \| 7d:4%")

    def test_cached_five_is_not_shown(self) -> None:
        (self.claude_home / ".statusline-cache.json").write_text(json.dumps(
            {"five": "40", "five_reset": str(WEEK_RESET)}))
        self.assertRegex(self.line3(), r"^Claude\s+5h:- \| ")

    # --- Go ---
    def go_line(self) -> str:
        return ANSI_ESCAPE.sub("", self.render()[3])

    def test_go_estimates_clamped_around_the_api_integer(self) -> None:
        self.write_go(3, 12, 6, est=(2.66, 12.4, 9.9))
        line = self.go_line()
        self.assertIn("5h:~2.7% (reset", line)
        self.assertIn("| wk:~12.4% (reset", line)
        self.assertIn("| mo:~6.4% (reset", line)

    def test_go_lower_clamp_and_floor_at_zero(self) -> None:
        self.write_go(3, 0, 1, est=(1.0, 0.0, 0.0))
        line = self.go_line()
        self.assertIn("5h:~2.5%", line)
        self.assertIn("| wk:~0.0%", line)
        self.assertIn("| mo:~0.5%", line)

    def test_old_go_summary_prints_integers(self) -> None:
        self.write_go(3, 12, 6, est=(2.66, 12.4, 6.2), age=GO_STALE_SECONDS + 60)
        self.assertRegex(self.go_line(), r"^Go\s+5h:3% \(reset .+\) \| wk:12% \(reset .+\) \| mo:6%")

    def test_passed_reset_still_shows_zero(self) -> None:
        self.write_go(42, 12, 6, est=(41.6, 12.4, 6.2), rolling_reset_in=-60)
        self.assertIn("5h:~0% | wk:~12.4%", self.go_line())

    def test_rate_limited_colour_follows_api(self) -> None:
        self.write_go(3, 12, 6, est=(2.66, 12.4, 6.2))
        cache = self.claude_home / ".statusline-go-usage.json"
        document = json.loads(cache.read_text())
        document["windows"]["rolling"]["status"] = "rate-limited"
        cache.write_text(json.dumps(document))
        self.assertIn(f"{RED}2.7%{RESET}", self.render()[3])


if __name__ == "__main__":
    unittest.main()
