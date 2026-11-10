"""Tests for scripts/statusline.sh on a fake HOME with a fake status-line payload."""
from __future__ import annotations

import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

STATUSLINE = SCRIPTS_DIR / "statusline.sh"
SKILL = "demo:skill"
EXPECTED_LINES = 3
# Lines 4+ printed after the rate-limit line when the transcript has a skill.
WRENCH = "\N{WRENCH}"
# statusline.sh calls last-skill.sh --color: only the note is dimmed, like "(high)" on line 2.
# Skill names use Claude Code's inline-code colour (truecolor rgb 177,185,249).
SKILL_COLOR = "\x1b[38;2;177;185;249m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
MAIN_NOTE = f"{DIM}(main){RESET}"
SKILL_BLOCK = [f"{WRENCH} {SKILL_COLOR}{SKILL}{RESET} {MAIN_NOTE}"]
CACHE_NAME = ".statusline-cache.json"
FIVE_PCT = 12.3
WEEK_PCT = 85
CONTEXT_PCT = 55.4
RESET_EPOCH = 1760000000
# 1200 + 300 + 5000 tokens -> "6.5k".
USAGE = {"input_tokens": 1200, "output_tokens": 300, "cache_read_input_tokens": 5000}
EXPECTED_TOKENS = "tokens:\x1b[0m6.5k"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
GO_STATE_ENV = "HYBRID_HANDS_STATE_DIR"
GO_MODEL = "deepseek-v4.1-flash"
GO_SUMMARY = "go_usage_summary.json"
STALE_SECONDS = 5 * 3600


def transcript_records(with_skill: bool = True) -> list[dict]:
    records = [{"type": "assistant", "message": {"usage": USAGE, "content": [{"type": "text", "text": "hi"}]}}]
    if with_skill:
        records.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": SKILL}},
        ]}})
    return records


class StatuslineTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()
        self.workdir = self.home / "project"
        self.workdir.mkdir()
        self.state_dir = self.home / "go-state"
        self.transcript = self.home / "session.jsonl"
        self.write_transcript(with_skill=True)

    def write_transcript(self, with_skill: bool) -> None:
        lines = [json.dumps(record) for record in transcript_records(with_skill)]
        self.transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_go_summary(self, five: float, week: float, estimated: bool = True,
                         updated_at: int | None = None) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        document = {
            "updated_at": int(time.time()) if updated_at is None else updated_at,
            "models": {GO_MODEL: {
                "5h": {"percent": five, "estimated": estimated},
                "7d": {"percent": week, "estimated": estimated},
                "30d": {"percent": five, "estimated": estimated},
            }},
        }
        (self.state_dir / GO_SUMMARY).write_text(json.dumps(document), encoding="utf-8")

    def payload(self, with_rate_limits: bool) -> str:
        document = {
            "workspace": {"current_dir": str(self.workdir)},
            "transcript_path": str(self.transcript),
            "model": {"display_name": "Opus"},
            "effort": {"level": "high"},
            "context_window": {"used_percentage": CONTEXT_PCT},
        }
        if with_rate_limits:
            document["rate_limits"] = {
                "five_hour": {"used_percentage": FIVE_PCT, "resets_at": RESET_EPOCH},
                "seven_day": {"used_percentage": WEEK_PCT, "resets_at": RESET_EPOCH},
            }
        return json.dumps(document)

    def render(self, with_rate_limits: bool = True,
               go_state: Path | None = None) -> list[str]:
        env = clean_env(HOME=str(self.home))
        if go_state is not None:
            env[GO_STATE_ENV] = str(go_state)
        result = run_bash(STATUSLINE, [], env, stdin=self.payload(with_rate_limits), cwd=self.workdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split("\n")

    def test_three_lines_then_skill_block(self) -> None:
        lines = self.render()
        self.assertEqual(len(lines), EXPECTED_LINES + len(SKILL_BLOCK))
        plain = [ANSI_ESCAPE.sub("", line) for line in lines]
        self.assertTrue(plain[0].endswith(" project"))
        self.assertEqual(plain[1], "Opus(high) | tokens:6.5k | ctx:55%")
        self.assertIn(EXPECTED_TOKENS, lines[1])
        self.assertRegex(plain[2], r"^Claude v1 ultra\s+5h:12% \(reset .+\) \| 7d:85% \(reset .+\)$")
        self.assertEqual(lines[EXPECTED_LINES:], SKILL_BLOCK)
        self.assertIn(f"{DIM}(high){RESET}", lines[1])  # same style as the skill note

    def test_three_lines_unchanged_without_skill(self) -> None:
        with_skill = self.render()
        self.write_transcript(with_skill=False)
        without_skill = self.render()
        self.assertEqual(without_skill, with_skill[:EXPECTED_LINES])

    def test_skill_block_backslashes_stay_literal(self) -> None:
        skill = "demo:a\\nb\\t%s"
        self.transcript.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": skill}},
        ]}}) + "\n", encoding="utf-8")
        self.assertEqual(self.render()[EXPECTED_LINES:], [f"{WRENCH} {SKILL_COLOR}{skill}{RESET} {MAIN_NOTE}"])

    def test_rate_limits_are_cached_and_shown_stale(self) -> None:
        self.render(with_rate_limits=True)
        cache = json.loads((self.claude_home / CACHE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(cache["five"], str(FIVE_PCT))
        plain = ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2])
        # The original fixture's expired reset stays absent.
        self.assertRegex(plain, r"^Claude v1 ultra\s+5h:- \| 7d:~85% \(reset .+\)$")
        import time
        cache["five_reset"] = str(int(time.time()) + 3600)
        (self.claude_home / CACHE_NAME).write_text(json.dumps(cache), encoding="utf-8")
        plain = ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2])
        self.assertRegex(plain, r"^Claude v1 ultra\s+5h:~12% \(reset .+\) \|")
        cache["five_reset"] = str(int(time.time()) - 1)
        (self.claude_home / CACHE_NAME).write_text(json.dumps(cache), encoding="utf-8")
        self.assertIn("5h:-", ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2]))

    def test_placeholders_without_rate_limits_or_cache(self) -> None:
        plain = ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2])
        self.assertEqual(plain, "Claude v1 ultra  5h:- | 7d:--")

    def test_go_usage_on_its_own_line_under_claude_with_estimated_marks(self) -> None:
        self.write_go_summary(five=12.3, week=31)
        lines = self.render(go_state=self.state_dir)
        self.assertRegex(ANSI_ESCAPE.sub("", lines[2]), r"^Claude v1 ultra\s+5h:[^|]+ \| 7d:[^|]+$")
        self.assertEqual(lines[3:-1], SKILL_BLOCK)
        line = lines[-1]  # Go is the last status-line line, after the skill block
        plain = ANSI_ESCAPE.sub("", line)
        self.assertRegex(plain, r"^Go\s+DS 5h ~12\.3%\s+\| tuần ~31\.0%$")
        self.assertIn(f"{GREEN}12.3%{RESET}", line)
        self.assertIn(f"{GREEN}31.0%{RESET}", line)

    def test_go_usage_exact_and_fresh_has_no_tilde(self) -> None:
        self.write_go_summary(five=88, week=12, estimated=False)
        line = self.render(go_state=self.state_dir)[-1]
        plain = ANSI_ESCAPE.sub("", line)
        self.assertRegex(plain, r"^Go\s+DS 5h 88\.0%\s+\| tuần 12\.0%$")
        self.assertIn(f"{RED}88.0%{RESET}", line)
        self.assertIn(f"{GREEN}12.0%{RESET}", line)

    def test_go_usage_older_than_five_hours_is_marked_stale(self) -> None:
        self.write_go_summary(five=12, week=31, estimated=False,
                              updated_at=int(time.time()) - STALE_SECONDS - 60)
        plain = ANSI_ESCAPE.sub("", self.render(go_state=self.state_dir)[-1])
        self.assertRegex(plain, r"^Go\s+DS 5h ~12\.0%\s+\| tuần ~31\.0%$")

    def test_go_usage_missing_file_is_silent(self) -> None:
        lines = self.render(go_state=self.state_dir)
        self.assertEqual(len(lines), EXPECTED_LINES + len(SKILL_BLOCK))
        self.assertNotIn("DS ", ANSI_ESCAPE.sub("", "\n".join(lines)))

    def test_go_usage_broken_json_is_silent_and_exits_zero(self) -> None:
        self.state_dir.mkdir(parents=True)
        (self.state_dir / GO_SUMMARY).write_text("{broken", encoding="utf-8")
        lines = self.render(go_state=self.state_dir)
        self.assertEqual(len(lines), EXPECTED_LINES + len(SKILL_BLOCK))
        self.assertNotIn("DS ", ANSI_ESCAPE.sub("", "\n".join(lines)))


if __name__ == "__main__":
    unittest.main()
