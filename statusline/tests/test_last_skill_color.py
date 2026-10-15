"""Tests for the --color flag of last-skill.sh / last_skill.py (dimmed notes in parentheses)."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR
from test_last_skill import WRENCH, run_script, skill_call

sys.path.insert(0, str(SCRIPTS_DIR))
# The import below needs SCRIPTS_DIR on sys.path.
from last_skill import ANSI_DIM, ANSI_RESET, COLOR_FLAG  # noqa: E402

STATUSLINE = SCRIPTS_DIR / "statusline.sh"
SESSION_ID = "00000000-1111-2222-3333-444444444444"
MAIN_SKILL = "dev-workflow:dev-triage"
SUB_SKILL = "dev-workflow:bug-investigation"
# Contains parentheses on purpose: colouring must not depend on searching the text for "(".
DESCRIPTION = "Fix (a) bug"
TIMESTAMP = "2020-01-01T10:05:00.000Z"
ESCAPE = "\x1b"
# Shell assignments such as DIM="\033[2m" in statusline.sh.
SHELL_COLOR = re.compile(r'^(DIM|RESET)="([^"]*)"$', re.MULTILINE)


def shell_colors() -> dict:
    text = STATUSLINE.read_text(encoding="utf-8")
    return {name: value.replace("\\033", ESCAPE) for name, value in SHELL_COLOR.findall(text)}


class LastSkillColorTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.main = root / f"{SESSION_ID}.jsonl"
        self.main.write_text(json.dumps({**skill_call("m1", MAIN_SKILL), "timestamp": TIMESTAMP}) + "\n",
                             encoding="utf-8")
        subagents = root / SESSION_ID / "subagents"
        subagents.mkdir(parents=True)
        (subagents / "agent-a1.jsonl").write_text(
            json.dumps({**skill_call("s1", SUB_SKILL), "timestamp": TIMESTAMP}) + "\n", encoding="utf-8")
        (subagents / "agent-a1.meta.json").write_text(
            json.dumps({"agentType": "parallel-subagents:hand", "description": DESCRIPTION}), encoding="utf-8")

    def output(self, *flags: str) -> list:
        result = run_script([*flags, str(self.main)])
        self.assertEqual(result.returncode, 0)
        return result.stdout.split("\n")

    def test_plain_output_has_main_note_and_no_ansi(self) -> None:
        lines = self.output()
        self.assertEqual(lines, [f"{WRENCH} {MAIN_SKILL} (main)", f'{WRENCH} {SUB_SKILL} (hand: "{DESCRIPTION}")'])
        self.assertNotIn(ESCAPE, "".join(lines))

    def test_color_wraps_only_the_note(self) -> None:
        lines = self.output(COLOR_FLAG)
        self.assertEqual(lines, [
            f"{WRENCH} {MAIN_SKILL} {ANSI_DIM}(main){ANSI_RESET}",
            f'{WRENCH} {SUB_SKILL} {ANSI_DIM}(hand: "{DESCRIPTION}"){ANSI_RESET}',
        ])

    def test_color_flag_with_statusline_stdin(self) -> None:
        result = run_script([COLOR_FLAG], stdin=json.dumps({"transcript_path": str(self.main)}))
        self.assertEqual(result.stdout.split("\n")[0], f"{WRENCH} {MAIN_SKILL} {ANSI_DIM}(main){ANSI_RESET}")

    def test_codes_match_statusline_sh(self) -> None:
        self.assertEqual(shell_colors(), {"DIM": ANSI_DIM, "RESET": ANSI_RESET})


if __name__ == "__main__":
    unittest.main()
