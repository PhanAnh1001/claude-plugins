"""Tests for scripts/skill-notice.sh + skill_notice.py (PreToolUse hook on the Skill tool)."""
from __future__ import annotations

import json
import os
import subprocess
import unittest

from _support import PLUGIN_ROOT, SCRIPTS_DIR, SUBPROCESS_TIMEOUT_SECONDS

HOOK = SCRIPTS_DIR / "skill-notice.sh"
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"
HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}/scripts/skill-notice.sh"'
SKILL_NAME = "dev-workflow:trace-check"
EXPECTED_MESSAGE = f"\N{WRENCH} Skill: {SKILL_NAME}"
# Keys that would block or alter the tool call; the hook must never emit them.
FORBIDDEN_KEYS = {"permissionDecision", "decision", "continue", "hookSpecificOutput"}


def payload(tool_input: object) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": tool_input})


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
    return subprocess.run(
        ["bash", str(HOOK)], input=stdin, env=env, capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )


class SkillNoticeHookTest(unittest.TestCase):
    def assert_notice(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output, {"systemMessage": EXPECTED_MESSAGE})
        self.assertFalse(FORBIDDEN_KEYS & output.keys())

    def assert_silent(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_prints_only_system_message_with_skill_name(self) -> None:
        self.assert_notice(run_hook(payload({"skill": SKILL_NAME, "args": "--write"})))

    def test_accepts_fallback_field_names(self) -> None:
        for key in ("name", "command"):
            with self.subTest(key=key):
                self.assert_notice(run_hook(payload({key: SKILL_NAME})))

    def test_silent_when_skill_field_missing(self) -> None:
        self.assert_silent(run_hook(payload({"args": "x"})))

    def test_silent_when_skill_name_blank(self) -> None:
        self.assert_silent(run_hook(payload({"skill": "  "})))

    def test_silent_when_tool_input_not_object(self) -> None:
        self.assert_silent(run_hook(payload("dev-workflow:trace-check")))

    def test_silent_on_invalid_json(self) -> None:
        self.assert_silent(run_hook("{not json"))

    def test_silent_on_empty_stdin(self) -> None:
        self.assert_silent(run_hook(""))

    def test_hook_is_executable(self) -> None:
        self.assertTrue(os.access(HOOK, os.X_OK))


class HooksJsonTest(unittest.TestCase):
    def test_pre_tool_use_skill_points_to_script(self) -> None:
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        groups = config["hooks"]["PreToolUse"]
        skill_groups = [group for group in groups if group.get("matcher") == "Skill"]
        self.assertEqual(len(skill_groups), 1)
        commands = [hook["command"] for hook in skill_groups[0]["hooks"]]
        self.assertEqual(commands, [HOOK_COMMAND])

    def test_session_start_hook_kept(self) -> None:
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        self.assertIn("SessionStart", config["hooks"])


if __name__ == "__main__":
    unittest.main()
