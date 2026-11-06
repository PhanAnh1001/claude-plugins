"""Tests for scripts/session-lines.sh and its block inside statusline.sh."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

SESSION_LINES = SCRIPTS_DIR / "session-lines.sh"
STATUSLINE = SCRIPTS_DIR / "statusline.sh"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
STALE_SECONDS = 1800


def dead_pid() -> int:
    child = subprocess.Popen(["true"])
    child.wait()
    return child.pid


def group(root: str, claude: float, go: float | None = 0.0, name: str = "", alias: str = "",
          members: list[str] | None = None) -> dict:
    return {"root": root, "name": name, "alias": alias, "members": members or [root],
            "claude_usd": claude * 12, "claude_pct": claude,
            "go_usd": None if go is None else go / 2, "go_pct": go}


class SessionLinesBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()

    def env(self) -> dict[str, str]:
        return clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home))

    def write(self, groups: list[dict], go_week: bool = True, calibrated: bool = True,
              age: int = 0) -> None:
        document = {"version": 2, "computed_at": int(time.time()) - age,
                    "rate_label": "calib" if calibrated else "prior", "groups": groups}
        if go_week:
            document["go_week"] = {"window_start": 1, "limit_usd": 50.0}
        (self.claude_home / ".statusline-week-split.json").write_text(json.dumps(document))

    def lines(self, sid: str = "", color: bool = False) -> list[str]:
        args = (["--color"] if color else []) + [sid]
        result = run_bash(SESSION_LINES, args, self.env())
        self.assertEqual(result.returncode, 0, result.stderr)
        return ANSI_ESCAPE.sub("", result.stdout).splitlines()


class SessionLinesTest(SessionLinesBase):
    def test_current_group_first_then_by_claude_desc(self) -> None:
        self.write([group("A", 5.0, 1.0, "alpha", "Việc A"), group("B", 2.0, 0.0, "beta"),
                    group("C", 9.0, 3.25, "gamma")])
        self.assertEqual(self.lines("B"), [
            "\u25b6\ufe0e beta           Claude 2.0% | Go 0.0%",
            "· gamma          Claude 9.0% | Go 3.2%",
            "· alpha  Việc A  Claude 5.0% | Go 1.0%"])

    def test_at_most_five_lines_and_zero_groups_hidden(self) -> None:
        groups = [group(f"S{i}", float(i)) for i in range(1, 8)] + [group("Z", 0.0), group("Y", 0.0)]
        self.write(groups)
        lines = self.lines("Y")
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "\u25b6\ufe0e Y   Claude 0.0% | Go 0.0%")
        self.assertTrue(lines[1].startswith("· S7  Claude 7.0%"))
        self.assertFalse(any(" Z " in line for line in lines))

    def test_names_alias_and_cut(self) -> None:
        self.write([group("A", 3.0, name="same", alias="same"),
                    group("B", 2.0, alias="chỉ có alias"),
                    group("C1234567890", 1.0),
                    group("D", 0.5, name="n" * 30, alias="a\tb\x01" + "x" * 40)])
        self.assertEqual(self.lines(), [
            f"· same{' ' * 12}  {' ' * 16}  Claude 3.0% | Go 0.0%",
            f"· B{' ' * 15}  chỉ có alias{' ' * 4}  Claude 2.0% | Go 0.0%",
            f"· C1234567{' ' * 8}  {' ' * 16}  Claude 1.0% | Go 0.0%",
            f"· {'n' * 15}…  a b {'x' * 11}…  Claude 0.5% | Go 0.0%"])

    def test_no_line_starts_with_whitespace_and_prefixes_same_width(self) -> None:
        self.write([group("A", 2.0, name="alpha"), group("B", 1.0, name="beta")])
        lines = self.lines("A")
        self.assertEqual(len(lines), 2)
        self.assertFalse(any(line[:1].isspace() for line in lines), lines)
        current, other = (line.replace("\ufe0e", "") for line in lines)
        self.assertEqual(current.index("alpha"), other.index("beta"))

    def test_side_session_selects_its_root_group(self) -> None:
        self.write([group("A", 1.0, name="main", members=["A", "B", "C"]), group("X", 4.0)])
        self.assertEqual(self.lines("C")[0], "\u25b6\ufe0e main  Claude 1.0% | Go 0.0%")

    def test_go_unknown_prints_dash(self) -> None:
        self.write([group("A", 1.0, go=None)], go_week=False)
        self.assertEqual(self.lines("A"), ["\u25b6\ufe0e A  Claude 1.0% | Go -"])
        self.assertEqual(self.lines("new-session"),
                         ["\u25b6\ufe0e new-sess  Claude 0.0% | Go -", "· A         Claude 1.0% | Go -"])

    def test_tilde_when_prior_or_old(self) -> None:
        self.write([group("A", 1.0)], calibrated=False)
        self.assertEqual(self.lines(), ["· A  Claude ~1.0% | Go ~0.0%"])
        self.write([group("A", 1.0)], age=STALE_SECONDS + 60)
        self.assertEqual(self.lines(), ["· A  Claude ~1.0% | Go ~0.0%"])

    def test_percent_columns_padded(self) -> None:
        self.write([group("A", 12.4, 0.0, "a"), group("B", 0.9, 10.0, "b")], go_week=True)
        self.assertEqual(self.lines("A"), ["\u25b6\ufe0e a  Claude 12.4% | Go  0.0%",
                                           "· b  Claude  0.9% | Go 10.0%"])
        self.write([group("A", 1.0, None), group("B", 1.0, 10.0)])
        self.assertEqual(self.lines(), ["· A  Claude 1.0% | Go     -", "· B  Claude 1.0% | Go 10.0%"])

    def test_colour_and_name_stays_literal(self) -> None:
        self.write([group("A", 85.0, 55.0, name="a\\nb %s")])
        result = run_bash(SESSION_LINES, ["--color", "A"], self.env())
        self.assertIn("\x1b[31m85.0%", result.stdout)
        self.assertIn("\x1b[33m55.0%", result.stdout)
        self.assertIn("a\\nb %s", result.stdout)

    def test_no_summary_prints_nothing(self) -> None:
        self.assertEqual(self.lines("A"), [])

    def test_statusline_places_block_after_go_before_skills(self) -> None:
        state = self.home / "go-state"
        state.mkdir()
        (state / "go_usage_summary.json").write_text(json.dumps({
            "updated_at": int(time.time()),
            "models": {"deepseek-x": {"5h": {"percent": 1}, "7d": {"percent": 2}}}}))
        self.write([group("A", 1.0, name="main")])
        payload = json.dumps({"workspace": {"current_dir": str(self.home)}, "session_id": "A",
                              "model": {"display_name": "Opus"}})
        env = clean_env(HOME=str(self.home), CLAUDE_HOME=str(self.claude_home),
                        HYBRID_HANDS_STATE_DIR=str(state), STATUSLINE_GO_LIVE="0")
        result = run_bash(STATUSLINE, [], env, stdin=payload, cwd=self.home)
        lines = ANSI_ESCAPE.sub("", result.stdout).split("\n")
        self.assertTrue(lines[3].startswith("Go"), lines)
        self.assertIn("DS 5h", lines[3])
        self.assertEqual(lines[4], "\u25b6\ufe0e main  Claude 1.0% | Go 0.0%")


class SessionRegistryTest(SessionLinesBase):
    """Liveness filter and names from Claude Code's session registry ($CLAUDE_HOME/sessions)."""

    def setUp(self) -> None:
        super().setUp()
        self.registry = self.claude_home / "sessions"
        self.registry.mkdir()
        self.live_pid = os.getpid()
        self.dead_pid = dead_pid()

    def register(self, file: str, pid: int, sid: str, name: str = "", source: str = "derived",
                 updated: int = 1) -> None:
        (self.registry / f"{file}.json").write_text(json.dumps(
            {"pid": pid, "sessionId": sid, "name": name, "nameSource": source, "updatedAt": updated}))

    def test_dead_group_hidden_and_live_zero_group_shown(self) -> None:
        self.write([group("A", 5.0, name="alpha"), group("B", 0.0, 0.0, name="beta")])
        self.register("1", self.dead_pid, "A")
        self.register("2", self.live_pid, "B")
        self.assertEqual(self.lines("CUR"), ["\u25b6\ufe0e CUR   Claude 0.0% | Go 0.0%",
                                             "· beta  Claude 0.0% | Go 0.0%"])

    def test_derived_name_used_when_summary_has_none(self) -> None:
        self.write([group("A", 1.0, alias="Việc A")])
        self.register("1", self.live_pid, "A", "ai-luxian-06")
        self.assertEqual(self.lines("A"), ["\u25b6\ufe0e ai-luxian-06  Việc A  Claude 1.0% | Go 0.0%"])

    def test_user_name_wins_over_newer_derived(self) -> None:
        self.write([group("A", 1.0, name="summary")])
        self.register("1", self.live_pid, "A", "luxian-b", "user", updated=1)
        self.register("2", self.live_pid, "A", "ai-luxian-07", "derived", updated=9)
        self.assertEqual(self.lines(), ["· luxian-b  Claude 1.0% | Go 0.0%"])

    def test_live_side_session_keeps_root_group(self) -> None:
        self.write([group("A", 1.0, name="main", members=["A", "S"])])
        self.register("1", self.dead_pid, "A", "root-name")
        self.register("2", self.live_pid, "S", "side")
        self.assertEqual(self.lines(), ["· main  Claude 1.0% | Go 0.0%"])

    def test_current_group_shown_even_when_dead(self) -> None:
        self.write([group("A", 1.0, name="main")])
        self.assertEqual(self.lines("A"), ["\u25b6\ufe0e main  Claude 1.0% | Go 0.0%"])

    def test_corrupt_file_does_not_break(self) -> None:
        self.write([group("A", 1.0), group("B", 2.0)])
        (self.registry / "9.json").write_text("{not json")
        self.register("1", self.live_pid, "A", "a-live")
        self.assertEqual(self.lines(), ["· a-live  Claude 1.0% | Go 0.0%"])


if __name__ == "__main__":
    unittest.main()
