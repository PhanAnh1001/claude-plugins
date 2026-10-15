"""Tests for scripts/statusline.sh on a fake HOME with a fake status-line payload."""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

STATUSLINE = SCRIPTS_DIR / "statusline.sh"
SKILL = "demo:skill"
EXPECTED_LINES = 3
# Lines 4+ printed after the rate-limit line when the transcript has a skill.
WRENCH = "\N{WRENCH}"
SKILL_BLOCK = [f"{WRENCH} {SKILL}"]
CACHE_NAME = ".statusline-cache.json"
FIVE_PCT = 12.3
WEEK_PCT = 85
CONTEXT_PCT = 55.4
RESET_EPOCH = 1760000000
# 1200 + 300 + 5000 tokens -> "6.5k".
USAGE = {"input_tokens": 1200, "output_tokens": 300, "cache_read_input_tokens": 5000}
EXPECTED_TOKENS = "tokens:\x1b[0m6.5k"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


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
        self.transcript = self.home / "session.jsonl"
        self.write_transcript(with_skill=True)

    def write_transcript(self, with_skill: bool) -> None:
        lines = [json.dumps(record) for record in transcript_records(with_skill)]
        self.transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

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

    def render(self, with_rate_limits: bool = True) -> list[str]:
        env = clean_env(HOME=str(self.home))
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
        self.assertRegex(plain[2], r"^5h:12%\(reset .+\) \| 7d:85%\(reset .+\)$")
        self.assertEqual(lines[EXPECTED_LINES:], SKILL_BLOCK)

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
        self.assertEqual(self.render()[EXPECTED_LINES:], [f"{WRENCH} {skill}"])

    def test_rate_limits_are_cached_and_shown_stale(self) -> None:
        self.render(with_rate_limits=True)
        cache = json.loads((self.claude_home / CACHE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(cache["five"], str(FIVE_PCT))
        plain = ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2])
        self.assertRegex(plain, r"^5h:~12%\(reset .+\) \| 7d:~85%\(reset .+\)$")

    def test_placeholders_without_rate_limits_or_cache(self) -> None:
        plain = ANSI_ESCAPE.sub("", self.render(with_rate_limits=False)[2])
        self.assertEqual(plain, "5h:-- | 7d:--")


if __name__ == "__main__":
    unittest.main()
