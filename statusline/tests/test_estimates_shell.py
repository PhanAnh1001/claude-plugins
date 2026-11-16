"""Tests for the decimal estimate on line 3 (Claude 7d) of statusline.sh."""
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
ESTIMATE_FRESH_SECONDS = 1800


class EstimateShellTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()

    def write_summary(self, pct: float = 4.3, base: float = 4, reset: int = WEEK_RESET,
                      age: int = 0) -> None:
        (self.claude_home / ".statusline-week-split.json").write_text(json.dumps({
            "version": 2, "computed_at": int(time.time()) - age, "reset": reset,
            "claude_estimates": {"week": {"pct": pct, "base": base, "reset": reset,
                                          "label": "calib"}}}))

    def render(self, week: float | None = 4, five: float | None = None) -> list[str]:
        limits = {}
        if week is not None:
            limits["seven_day"] = {"used_percentage": week, "resets_at": WEEK_RESET}
        if five is not None:
            limits["five_hour"] = {"used_percentage": five, "resets_at": WEEK_RESET}
        payload = {"workspace": {"current_dir": str(self.home)}, "model": {"display_name": "O"}}
        if limits:
            payload["rate_limits"] = limits
        env = clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home))
        result = run_bash(STATUSLINE, [], env, stdin=json.dumps(payload), cwd=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split("\n")

    def line3(self, **kwargs) -> str:
        return ANSI_ESCAPE.sub("", self.render(**kwargs)[2])

    # --- Claude 7d ---
    def test_estimate_shown_with_one_decimal_and_integer_colour(self) -> None:
        self.write_summary()
        lines = self.render()
        self.assertRegex(ANSI_ESCAPE.sub("", lines[2]), r"^Claude v1 ultra\s+5h:- \| 7d:~4\.3% \(reset .+\)$")
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
        self.assertRegex(self.line3(week=None), r"^Claude v1 ultra\s+5h:- \| 7d:~4\.3% \(reset .+\)$")

    def test_live_five_still_printed(self) -> None:
        self.assertRegex(self.line3(five=12.3), r"^Claude v1 ultra\s+5h:12% \(reset .+\) \| 7d:4%")

    def test_cached_five_with_future_reset_is_shown_stale(self) -> None:
        (self.claude_home / ".statusline-cache.json").write_text(json.dumps(
            {"five": "40", "five_reset": str(WEEK_RESET)}))
        self.assertRegex(self.line3(), r"^Claude v1 ultra\s+5h:~40% \(reset .+\) \| ")


if __name__ == "__main__":
    unittest.main()
