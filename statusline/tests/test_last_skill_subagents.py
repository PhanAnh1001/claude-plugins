"""Tests for last_skill.py reading subagent transcripts (<session>/subagents/agent-*.jsonl).

Fixtures follow the layout Claude Code writes: <dir>/<session_id>.jsonl for the main agent,
<dir>/<session_id>/subagents/agent-<id>.jsonl plus agent-<id>.meta.json for each subagent.
Expected output: "🔧 <skill>" for the main agent, then '🔧 <skill> (<agent>: "<description start>")'
per subagent, newest load first, with no header line.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from _support import SCRIPTS_DIR
from test_last_skill import WRENCH, hook_message, run_script, skill_call, text_message

sys.path.insert(0, str(SCRIPTS_DIR))
# The imports below need SCRIPTS_DIR on sys.path.
from last_skill import MAX_SUBAGENT_FILES, MAX_SUBAGENT_LINES  # noqa: E402
from subagent_skills import SUBAGENT_DESCRIPTION_MAX_CHARS  # noqa: E402

SESSION_ID = "00000000-1111-2222-3333-444444444444"
MAIN_SKILL = "dev-workflow:dev-triage"
SUB_SKILL = "dev-workflow:bug-investigation"
OTHER_SUB_SKILL = "summary-first-docs:structuring-documents"
HAND_AGENT_TYPE = "parallel-subagents:hand"
HAND = "hand"
DEFAULT_AGENT = "subagent"
DESCRIPTION = "Nạp skill để thử statusline"
OTHER_DESCRIPTION = "Viết docs solutions và ADR-003"
# The first SUBAGENT_DESCRIPTION_MAX_CHARS (15) characters of the descriptions above.
DESCRIPTION_START = "Nạp skill để th"
OTHER_DESCRIPTION_START = "Viết docs solut"
OLD_HEADER = "skill:"
EARLY = "2020-01-01T10:00:00.000Z"
MIDDLE = "2020-01-01T10:01:00.000Z"
LATE = "2020-01-01T10:05:00.000Z"
# File mtimes used when a test needs a fixed order; all later than EARLY, MIDDLE and LATE.
BASE_MTIME = 1_700_000_000


def stamped(record: dict, timestamp: str) -> dict:
    return {**record, "timestamp": timestamp}


def meta_json(description: Optional[str] = DESCRIPTION, agent_type: Optional[str] = HAND_AGENT_TYPE) -> str:
    meta: dict = {"spawnDepth": 1}
    if description is not None:
        meta["description"] = description
    if agent_type is not None:
        meta["agentType"] = agent_type
    return json.dumps(meta, ensure_ascii=False)


def main_line(skill: str) -> str:
    return f"{WRENCH} {skill}"


def sub_line(skill: str, agent: str = HAND, description: Optional[str] = DESCRIPTION_START) -> str:
    label = f'{agent}: "{description}"' if description else agent
    return f"{WRENCH} {skill} ({label})"


def lines(*rendered: str) -> str:
    return "\n".join(rendered)


class SubagentSkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.main = self.root / f"{SESSION_ID}.jsonl"
        self.subagents = self.root / SESSION_ID / "subagents"

    @staticmethod
    def write_jsonl(path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    def write_main(self, records: list[dict]) -> None:
        self.write_jsonl(self.main, records)

    def write_subagent(
        self, agent_id: str, records: list[dict], meta: Optional[str] = None, mtime: Optional[float] = None,
    ) -> Path:
        transcript = self.subagents / f"agent-{agent_id}.jsonl"
        self.write_jsonl(transcript, records)
        if meta is not None:
            (self.subagents / f"agent-{agent_id}.meta.json").write_text(meta, encoding="utf-8")
        if mtime is not None:
            os.utime(transcript, (mtime, mtime))
        return transcript

    def write_skill_subagent(self, agent_id: str, skill: str, timestamp: str, meta: Optional[str]) -> Path:
        return self.write_subagent(agent_id, [stamped(skill_call(f"s-{agent_id}", skill), timestamp)], meta=meta)

    def assert_output(self, expected: str) -> None:
        result = run_script([str(self.main)])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, expected)

    def test_main_then_subagents_newest_first(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), LATE)])
        self.write_skill_subagent("a1", OTHER_SUB_SKILL, EARLY, meta_json(OTHER_DESCRIPTION))
        self.write_subagent("a2", [
            stamped(skill_call("s1", SUB_SKILL), MIDDLE), stamped(hook_message("s1", SUB_SKILL), MIDDLE),
        ], meta=meta_json(DESCRIPTION))
        self.assert_output(lines(
            main_line(MAIN_SKILL), sub_line(SUB_SKILL),
            sub_line(OTHER_SUB_SKILL, description=OTHER_DESCRIPTION_START),
        ))

    def test_no_header_line(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json())
        result = run_script([str(self.main)])
        self.assertNotIn(OLD_HEADER, result.stdout.split("\n"))
        self.assertTrue(all(line.startswith(f"{WRENCH} ") for line in result.stdout.split("\n")))

    def test_only_main(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("a1", [stamped(text_message("work"), LATE)], meta=meta_json())
        self.assert_output(main_line(MAIN_SKILL))

    def test_only_subagent(self) -> None:
        self.write_main([stamped(text_message("hi"), EARLY)])
        self.write_subagent("a1", [stamped(hook_message("s1", SUB_SKILL), LATE)], meta=meta_json())
        self.assert_output(sub_line(SUB_SKILL))

    def test_no_skill_anywhere_prints_nothing(self) -> None:
        self.write_main([stamped(text_message("hi"), EARLY)])
        self.write_subagent("a1", [stamped(text_message("work"), LATE)], meta=meta_json())
        self.assert_output("")

    def test_missing_main_transcript_still_shows_subagents(self) -> None:
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json())
        self.assertFalse(self.main.exists())
        self.assert_output(sub_line(SUB_SKILL))

    def test_no_subagents_dir(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.assertFalse(self.subagents.exists())
        self.assert_output(main_line(MAIN_SKILL))

    def test_subagents_path_is_a_file(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.subagents.parent.mkdir(parents=True)
        self.subagents.write_text("not a directory", encoding="utf-8")
        self.assert_output(main_line(MAIN_SKILL))

    def test_long_description_is_cut_without_ellipsis(self) -> None:
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json(DESCRIPTION))
        self.assertEqual(len(DESCRIPTION_START), SUBAGENT_DESCRIPTION_MAX_CHARS)
        self.assert_output(sub_line(SUB_SKILL, description=DESCRIPTION_START))

    def test_cut_description_drops_trailing_space(self) -> None:
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json("Nghiên cứu API của EasyHRM"))
        self.assert_output(sub_line(SUB_SKILL, description="Nghiên cứu API"))

    def test_description_at_limit_is_kept_whole(self) -> None:
        description = "y" * SUBAGENT_DESCRIPTION_MAX_CHARS
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json(description))
        self.assert_output(sub_line(SUB_SKILL, description=description))

    def test_description_quotes_colon_and_whitespace(self) -> None:
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json('  E6:\t"x"\n và  push'))
        self.assert_output(sub_line(SUB_SKILL, description="E6: 'x' và push"))

    def test_meta_without_description_prints_agent_only(self) -> None:
        cases = {
            "plugin agent": (meta_json(None), HAND),
            "plain agent": (meta_json(None, "Explore"), "Explore"),
            "blank description": (meta_json("   "), HAND),
        }
        self.write_main([])
        for name, (meta, agent) in cases.items():
            with self.subTest(case=name):
                self.write_skill_subagent("a1", SUB_SKILL, LATE, meta)
                self.assert_output(sub_line(SUB_SKILL, agent=agent, description=None))

    def test_meta_without_agent_type(self) -> None:
        cases = {
            "no agentType": (meta_json(DESCRIPTION, None), DESCRIPTION_START),
            "blank agentType": (meta_json(DESCRIPTION, " "), DESCRIPTION_START),
            "no fields": (meta_json(None, None), None),
        }
        self.write_main([])
        for name, (meta, description) in cases.items():
            with self.subTest(case=name):
                self.write_skill_subagent("a1", SUB_SKILL, LATE, meta)
                self.assert_output(sub_line(SUB_SKILL, agent=DEFAULT_AGENT, description=description))

    def test_meta_missing_or_broken(self) -> None:
        cases = {"missing": None, "bad-json": "{not json", "not-object": json.dumps(["hand"])}
        self.write_main([])
        for name, meta in cases.items():
            with self.subTest(meta=name):
                for leftover in self.subagents.glob("*") if self.subagents.exists() else []:
                    leftover.unlink()
                self.write_skill_subagent("a1", SUB_SKILL, LATE, meta)
                self.assert_output(sub_line(SUB_SKILL, agent=DEFAULT_AGENT, description=None))

    def test_at_most_max_subagent_lines(self) -> None:
        self.write_main([])
        count = MAX_SUBAGENT_LINES + 1
        for index in range(count):
            self.write_skill_subagent(
                f"a{index}", f"demo:skill-{index}", f"2020-01-01T10:0{index}:00.000Z", meta_json(f"task {index}"),
            )
        newest_first = [sub_line(f"demo:skill-{index}", description=f"task {index}") for index in reversed(range(count))]
        self.assert_output(lines(*newest_first[:MAX_SUBAGENT_LINES]))

    def test_only_newest_files_by_mtime_are_scanned(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("old", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=meta_json(),
                            mtime=BASE_MTIME)
        for index in range(MAX_SUBAGENT_FILES):
            self.write_subagent(f"new{index}", [stamped(text_message("work"), LATE)], meta=meta_json(),
                                mtime=BASE_MTIME + index + 1)
        self.assert_output(main_line(MAIN_SKILL))
        (self.subagents / "agent-new0.jsonl").unlink()  # now "old" is within the window
        self.assert_output(lines(main_line(MAIN_SKILL), sub_line(SUB_SKILL)))

    def test_hit_without_timestamp_is_ordered_by_file_mtime(self) -> None:
        self.write_main([skill_call("m1", MAIN_SKILL)])
        self.write_subagent("a1", [skill_call("s1", SUB_SKILL)], meta=meta_json(DESCRIPTION), mtime=BASE_MTIME)
        self.write_skill_subagent("a2", OTHER_SUB_SKILL, LATE, meta_json(OTHER_DESCRIPTION))
        self.assert_output(lines(
            main_line(MAIN_SKILL), sub_line(SUB_SKILL),
            sub_line(OTHER_SUB_SKILL, description=OTHER_DESCRIPTION_START),
        ))

    def test_bad_subagent_lines_fail_open(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        transcript = self.write_subagent("a1", [], meta=meta_json())
        transcript.write_bytes(b'{"Skill" broken\n\xff\xfe"Skill"\n')
        self.assert_output(main_line(MAIN_SKILL))


if __name__ == "__main__":
    unittest.main()
