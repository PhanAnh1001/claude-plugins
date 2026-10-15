"""Tests for last_skill.py reading subagent transcripts (<session>/subagents/agent-*.jsonl).

Fixtures follow the layout Claude Code writes: <dir>/<session_id>.jsonl for the main agent,
<dir>/<session_id>/subagents/agent-<id>.jsonl plus agent-<id>.meta.json for each subagent.
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
from last_skill import MAX_SUBAGENT_FILES  # noqa: E402  (needs SCRIPTS_DIR on sys.path)

SESSION_ID = "00000000-1111-2222-3333-444444444444"
MAIN_SKILL = "dev-workflow:dev-triage"
SUB_SKILL = "dev-workflow:bug-investigation"
HAND_AGENT_TYPE = "parallel-subagents:hand"
HAND_LABEL = "hand"
DEFAULT_LABEL = "subagent"
EARLY = "2020-01-01T10:00:00.000Z"
MIDDLE = "2020-01-01T10:01:00.000Z"
LATE = "2020-01-01T10:05:00.000Z"
OTHER_SUB_SKILL = "summary-first-docs:structuring-documents"
# File mtimes used when a test needs a fixed order; all later than EARLY and LATE.
BASE_MTIME = 1_700_000_000


def stamped(record: dict, timestamp: str) -> dict:
    return {**record, "timestamp": timestamp}


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

    def write_main(self, records: list[dict]) -> str:
        self.write_jsonl(self.main, records)
        return str(self.main)

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

    @staticmethod
    def hand_meta(agent_type: str = HAND_AGENT_TYPE) -> str:
        return json.dumps({"agentType": agent_type, "description": "fixture", "spawnDepth": 1})

    def assert_output(self, expected: str) -> None:
        result = run_script([str(self.main)])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, expected)

    def test_subagent_skill_newer_than_main(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("a1", [
            stamped(skill_call("s1", SUB_SKILL), LATE), stamped(hook_message("s1", SUB_SKILL), LATE),
        ], meta=self.hand_meta())
        self.assert_output(f"{WRENCH} {SUB_SKILL} ({HAND_LABEL})")

    def test_main_skill_newer_than_subagent(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), LATE)])
        self.write_subagent("a1", [stamped(skill_call("s1", SUB_SKILL), EARLY)], meta=self.hand_meta())
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")

    def test_subagent_only_skill(self) -> None:
        self.write_main([stamped(text_message("hi"), EARLY)])
        self.write_subagent("a1", [stamped(hook_message("s1", SUB_SKILL), LATE)], meta=self.hand_meta())
        self.assert_output(f"{WRENCH} {SUB_SKILL} ({HAND_LABEL})")

    def test_no_subagents_dir(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.assertFalse(self.subagents.exists())
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")

    def test_subagents_path_is_a_file(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.subagents.parent.mkdir(parents=True)
        self.subagents.write_text("not a directory", encoding="utf-8")
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")

    def test_meta_missing_or_broken(self) -> None:
        cases = {
            "missing": None,
            "bad-json": "{not json",
            "not-object": json.dumps(["hand"]),
            "no-agent-type": json.dumps({"description": "x"}),
            "empty-agent-type": json.dumps({"agentType": " "}),
        }
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        for name, meta in cases.items():
            with self.subTest(meta=name):
                for leftover in self.subagents.glob("*") if self.subagents.exists() else []:
                    leftover.unlink()
                self.write_subagent("a1", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=meta)
                self.assert_output(f"{WRENCH} {SUB_SKILL} ({DEFAULT_LABEL})")

    def test_agent_type_without_plugin_prefix(self) -> None:
        self.write_main([])
        self.write_subagent("a1", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=self.hand_meta("Explore"))
        self.assert_output(f"{WRENCH} {SUB_SKILL} (Explore)")

    def test_only_newest_files_by_mtime_are_scanned(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        # The oldest-modified file holds the newest skill but falls outside the scan window.
        self.write_subagent("old", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=self.hand_meta(),
                            mtime=BASE_MTIME)
        for index in range(MAX_SUBAGENT_FILES):
            self.write_subagent(f"new{index}", [stamped(text_message("work"), LATE)], meta=self.hand_meta(),
                                mtime=BASE_MTIME + index + 1)
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")
        (self.subagents / "agent-new0.jsonl").unlink()  # now "old" is within the window
        self.assert_output(f"{WRENCH} {SUB_SKILL} ({HAND_LABEL})")

    def test_newest_of_several_subagents(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("a1", [stamped(skill_call("s1", OTHER_SUB_SKILL), MIDDLE)],
                            meta=self.hand_meta(), mtime=BASE_MTIME + 2)
        self.write_subagent("a2", [stamped(skill_call("s2", SUB_SKILL), LATE)],
                            meta=self.hand_meta("general-purpose"), mtime=BASE_MTIME + 1)
        self.assert_output(f"{WRENCH} {SUB_SKILL} (general-purpose)")

    def test_main_hit_without_timestamp_is_kept(self) -> None:
        self.write_main([skill_call("m1", MAIN_SKILL)])
        self.write_subagent("a1", [stamped(skill_call("s1", SUB_SKILL), LATE)], meta=self.hand_meta())
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")

    def test_subagent_hit_without_timestamp_is_ignored(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        self.write_subagent("a1", [skill_call("s1", SUB_SKILL)], meta=self.hand_meta())
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")

    def test_bad_subagent_lines_fail_open(self) -> None:
        self.write_main([stamped(skill_call("m1", MAIN_SKILL), EARLY)])
        transcript = self.write_subagent("a1", [], meta=self.hand_meta())
        transcript.write_bytes(b'{"Skill" broken\n\xff\xfe"Skill"\n')
        self.assert_output(f"{WRENCH} {MAIN_SKILL}")


if __name__ == "__main__":
    unittest.main()
