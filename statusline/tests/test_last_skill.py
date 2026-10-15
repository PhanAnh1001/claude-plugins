"""Tests for scripts/last-skill.sh + last_skill.py (status-line helper: skill lines, main agent).

Ported from dev-workflow (commit 65f7f95) tests/test_last_skill.py; the env var name differs.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, SUBPROCESS_TIMEOUT_SECONDS

SCRIPT = SCRIPTS_DIR / "last-skill.sh"
MAX_BYTES_ENV = "STATUSLINE_LAST_SKILL_MAX_BYTES"
OLD_SKILL = "dev-workflow:dev-triage"
NEW_SKILL = "dev-workflow:trace-check"
HOOK_ONLY_SKILL = "jira-tools:jira"
WRENCH = "\N{WRENCH}"
# Filler text so the transcript is far larger than SMALL_MAX_BYTES.
FILLER_TEXT = "x" * 2000
FILLER_LINES = 20
SMALL_MAX_BYTES = 4096


def main_block(skill: str) -> str:
    """Output of last_skill.py when only the main agent loaded a skill."""
    return f"{WRENCH} {skill} (main)"


def assistant_tool_use(tool_id: str, name: str, tool_input: object) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input},
        ]},
    }


def skill_call(tool_id: str, skill: str) -> dict:
    return assistant_tool_use(tool_id, "Skill", {"skill": skill})


def hook_message(tool_id: str, skill: str) -> dict:
    return {"type": "attachment", "attachment": {
        "type": "hook_system_message", "content": f"{WRENCH} Skill: {skill}",
        "hookName": "PreToolUse:Skill", "toolUseID": tool_id, "hookEvent": "PreToolUse",
    }}


def text_message(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def filler() -> list[dict]:
    return [text_message(FILLER_TEXT) for _ in range(FILLER_LINES)]


def run_script(args: list[str], stdin: str = "", env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != MAX_BYTES_ENV}
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(SCRIPT), *args], input=stdin, env=env, capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )


class LastSkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.transcript = Path(self._tmp.name) / "session.jsonl"

    def write_transcript(self, records: list[dict], tail: str = "") -> str:
        lines = [json.dumps(record, ensure_ascii=False) for record in records]
        self.transcript.write_text("\n".join(lines) + "\n" + tail, encoding="utf-8")
        return str(self.transcript)

    def assert_skill(self, result: subprocess.CompletedProcess[str], skill: str) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, main_block(skill))

    def assert_silent(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_most_recent_of_several_skill_calls(self) -> None:
        path = self.write_transcript([
            skill_call("t1", OLD_SKILL), hook_message("t1", OLD_SKILL), *filler(),
            skill_call("t2", NEW_SKILL), hook_message("t2", NEW_SKILL), text_message("done"),
        ])
        self.assert_skill(run_script([path]), NEW_SKILL)

    def test_tool_use_without_hook(self) -> None:
        path = self.write_transcript([skill_call("t1", OLD_SKILL), text_message("done")])
        self.assert_skill(run_script([path]), OLD_SKILL)

    def test_hook_message_only(self) -> None:
        path = self.write_transcript([*filler(), hook_message("t9", HOOK_ONLY_SKILL), text_message("ok")])
        self.assert_skill(run_script([path]), HOOK_ONLY_SKILL)

    def test_hook_message_when_tool_use_has_no_name(self) -> None:
        path = self.write_transcript([
            skill_call("t1", OLD_SKILL), assistant_tool_use("t2", "Skill", {}), hook_message("t2", NEW_SKILL),
        ])
        self.assert_skill(run_script([path]), NEW_SKILL)

    def test_silent_without_skill_records(self) -> None:
        path = self.write_transcript([
            *filler(), assistant_tool_use("t1", "Bash", {"command": "ls"}), text_message("Skill"),
        ])
        self.assert_silent(run_script([path]))

    def test_silent_when_file_missing(self) -> None:
        self.assert_silent(run_script([str(Path(self._tmp.name) / "missing.jsonl")]))

    def test_ignores_cut_off_last_line(self) -> None:
        partial = json.dumps(skill_call("t2", NEW_SKILL))[:-10]
        path = self.write_transcript([skill_call("t1", OLD_SKILL), text_message("x")], tail=partial)
        self.assert_skill(run_script([path]), OLD_SKILL)

    def test_silent_when_only_line_is_cut_off(self) -> None:
        self.transcript.write_text(json.dumps(skill_call("t1", OLD_SKILL))[:-5], encoding="utf-8")
        self.assert_silent(run_script([str(self.transcript)]))

    def test_skill_beyond_read_limit_is_not_shown(self) -> None:
        path = self.write_transcript([skill_call("t1", OLD_SKILL), *filler()])
        self.assertGreater(self.transcript.stat().st_size, SMALL_MAX_BYTES)
        self.assert_silent(run_script([path], env_extra={MAX_BYTES_ENV: str(SMALL_MAX_BYTES)}))
        self.assert_skill(run_script([path]), OLD_SKILL)

    def test_skill_within_read_limit_is_shown(self) -> None:
        path = self.write_transcript([*filler(), skill_call("t1", NEW_SKILL), text_message("x")])
        self.assert_skill(run_script([path], env_extra={MAX_BYTES_ENV: str(SMALL_MAX_BYTES)}), NEW_SKILL)

    def test_reads_transcript_path_from_statusline_stdin(self) -> None:
        path = self.write_transcript([skill_call("t1", NEW_SKILL)])
        stdin = json.dumps({"transcript_path": path, "model": {"display_name": "Opus"}})
        self.assert_skill(run_script([], stdin=stdin), NEW_SKILL)

    def test_silent_on_bad_stdin(self) -> None:
        for stdin in ("", "{not json", json.dumps({"model": {}}), json.dumps([1, 2])):
            with self.subTest(stdin=stdin):
                self.assert_silent(run_script([], stdin=stdin))

    def test_script_is_executable(self) -> None:
        self.assertTrue(os.access(SCRIPT, os.X_OK))


if __name__ == "__main__":
    unittest.main()
