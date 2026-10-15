"""Tests for last_skill.py reading subagent transcripts (<session>/subagents/agent-*.jsonl).

Fixtures follow the layout Claude Code writes: <dir>/<session_id>.jsonl for the main agent,
<dir>/<session_id>/subagents/agent-<id>.jsonl plus agent-<id>.meta.json for each subagent.
Expected output is the block "skill:" / "main: <skill>" / "<subagent label>: <skill>".
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
from test_last_skill import BLOCK_HEADER, MAIN_LABEL, hook_message, run_script, skill_call, text_message

sys.path.insert(0, str(SCRIPTS_DIR))
# The imports below need SCRIPTS_DIR on sys.path.
from last_skill import MAX_SUBAGENT_FILES, MAX_SUBAGENT_LINES  # noqa: E402
from subagent_skills import LABEL_ELLIPSIS, SUBAGENT_LABEL_MAX_CHARS  # noqa: E402

SESSION_ID = "00000000-1111-2222-3333-444444444444"
MAIN_SKILL = "dev-workflow:dev-triage"
SUB_SKILL = "dev-workflow:bug-investigation"
OTHER_SUB_SKILL = "summary-first-docs:structuring-documents"
HAND_AGENT_TYPE = "parallel-subagents:hand"
HAND_LABEL = "hand"
DEFAULT_LABEL = "subagent"
DESCRIPTION = "Nạp skill để thử statusline"
OTHER_DESCRIPTION = "Viết docs solutions và ADR-003"
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


def block(*lines: tuple) -> str:
    return "\n".join([BLOCK_HEADER, *(f"{label}: {skill}" for label, skill in lines)])


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

    def test_full_block_main_then_subagents_newest_first(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), LATE)])
        self.write_skill_subagent("a1", OTHER_SUB_SKILL, EARLY, meta_json(OTHER_DESCRIPTION))
        self.write_subagent("a2", [
            stamped(skill_call("s1", SUB_SKILL), MIDDLE), stamped(hook_message("s1", SUB_SKILL), MIDDLE),
        ], meta=meta_json(DESCRIPTION))
        self.assert_output(block(
            (MAIN_LABEL, MAIN_SKILL), (DESCRIPTION, SUB_SKILL), (OTHER_DESCRIPTION, OTHER_SUB_SKILL),
        ))

    def test_only_main(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("a1", [stamped(text_message("work"), LATE)], meta=meta_json())
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL)))

    def test_only_subagent(self) -> None:
        self.write_main([stamped(text_message("hi"), EARLY)])
        self.write_subagent("a1", [stamped(hook_message("s1", SUB_SKILL), LATE)], meta=meta_json())
        self.assert_output(block((DESCRIPTION, SUB_SKILL)))

    def test_no_skill_anywhere_prints_nothing(self) -> None:
        self.write_main([stamped(text_message("hi"), EARLY)])
        self.write_subagent("a1", [stamped(text_message("work"), LATE)], meta=meta_json())
        self.assert_output("")

    def test_missing_main_transcript_still_shows_subagents(self) -> None:
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json())
        self.assertFalse(self.main.exists())
        self.assert_output(block((DESCRIPTION, SUB_SKILL)))

    def test_no_subagents_dir(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.assertFalse(self.subagents.exists())
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL)))

    def test_subagents_path_is_a_file(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.subagents.parent.mkdir(parents=True)
        self.subagents.write_text("not a directory", encoding="utf-8")
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL)))

    def test_long_description_is_cut_with_ellipsis(self) -> None:
        description = "Điều tra lỗi " + "x" * SUBAGENT_LABEL_MAX_CHARS
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json(description))
        expected_label = description[:SUBAGENT_LABEL_MAX_CHARS] + LABEL_ELLIPSIS
        self.assert_output(block((expected_label, SUB_SKILL)))

    def test_description_at_limit_is_not_cut(self) -> None:
        description = "y" * SUBAGENT_LABEL_MAX_CHARS
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json(description))
        self.assert_output(block((description, SUB_SKILL)))

    def test_description_colon_and_whitespace_are_cleaned(self) -> None:
        self.write_main([])
        self.write_skill_subagent("a1", SUB_SKILL, LATE, meta_json("  E6:\tcommit\n và   push  "))
        self.assert_output(block(("E6- commit và push", SUB_SKILL)))

    def test_meta_without_description_uses_agent_type(self) -> None:
        cases = {
            "plugin agent": (meta_json(None), HAND_LABEL),
            "plain agent": (meta_json(None, "Explore"), "Explore"),
            "blank description": (meta_json("   "), HAND_LABEL),
        }
        self.write_main([])
        for name, (meta, label) in cases.items():
            with self.subTest(case=name):
                self.write_skill_subagent("a1", SUB_SKILL, LATE, meta)
                self.assert_output(block((label, SUB_SKILL)))

    def test_meta_missing_or_broken(self) -> None:
        cases = {
            "missing": None,
            "bad-json": "{not json",
            "not-object": json.dumps(["hand"]),
            "no-fields": meta_json(None, None),
            "empty-agent-type": meta_json(None, " "),
        }
        self.write_main([])
        for name, meta in cases.items():
            with self.subTest(meta=name):
                for leftover in self.subagents.glob("*") if self.subagents.exists() else []:
                    leftover.unlink()
                self.write_skill_subagent("a1", SUB_SKILL, LATE, meta)
                self.assert_output(block((DEFAULT_LABEL, SUB_SKILL)))

    def test_at_most_max_subagent_lines(self) -> None:
        self.write_main([])
        count = MAX_SUBAGENT_LINES + 1
        for index in range(count):
            self.write_skill_subagent(
                f"a{index}", f"demo:skill-{index}", f"2020-01-01T10:0{index}:00.000Z", meta_json(f"task {index}"),
            )
        newest_first = [(f"task {index}", f"demo:skill-{index}") for index in reversed(range(count))]
        self.assert_output(block(*newest_first[:MAX_SUBAGENT_LINES]))

    def test_only_newest_files_by_mtime_are_scanned(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("old", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=meta_json(),
                            mtime=BASE_MTIME)
        for index in range(MAX_SUBAGENT_FILES):
            self.write_subagent(f"new{index}", [stamped(text_message("work"), LATE)], meta=meta_json(),
                                mtime=BASE_MTIME + index + 1)
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL)))
        (self.subagents / "agent-new0.jsonl").unlink()  # now "old" is within the window
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL), (DESCRIPTION, SUB_SKILL)))

    def test_hit_without_timestamp_is_ordered_by_file_mtime(self) -> None:
        self.write_main([skill_call("m1", MAIN_SKILL)])
        self.write_subagent("a1", [skill_call("s1", SUB_SKILL)], meta=meta_json(DESCRIPTION), mtime=BASE_MTIME)
        self.write_skill_subagent("a2", OTHER_SUB_SKILL, LATE, meta_json(OTHER_DESCRIPTION))
        self.assert_output(block(
            (MAIN_LABEL, MAIN_SKILL), (DESCRIPTION, SUB_SKILL), (OTHER_DESCRIPTION, OTHER_SUB_SKILL),
        ))

    def test_bad_subagent_lines_fail_open(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        transcript = self.write_subagent("a1", [], meta=meta_json())
        transcript.write_bytes(b'{"Skill" broken\n\xff\xfe"Skill"\n')
        self.assert_output(block((MAIN_LABEL, MAIN_SKILL)))


if __name__ == "__main__":
    unittest.main()
