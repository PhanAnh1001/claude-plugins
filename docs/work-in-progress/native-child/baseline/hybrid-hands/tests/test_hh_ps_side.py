"""`hh-ps` side-session v2: worktree scope, synthetic rows and nested text tree."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PLUGIN_LIB = TESTS.parent / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
sys.path.insert(0, str(TESTS / "fixtures" / "hh_ps"))

from fixture import MAIN_SESSION, NONAME_SESSION, SIDE_SESSION  # noqa: E402
from side_fixture import (  # noqa: E402
    DSH_SIDE, LOST_PARENT_SIDE, NESTED_SIDE, ORPHAN_SIDE, SideFixture, WT_SIDE,
)
from hh_ps import cli  # noqa: E402


class HhPsSideTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = SideFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str) -> tuple:
        out = io.StringIO()
        with self.fx.env(), redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.fx.project)])
        return code, out.getvalue()

    def json_cli(self, *args: str) -> dict:
        code, out = self.run_cli("--json", *args)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_claude_side_worktree_included_but_lost_parent_not(self) -> None:
        sessions = {item["session_id"]: item for item in self.json_cli()["sessions"]}
        self.assertIn(WT_SIDE, sessions)
        side = sessions[WT_SIDE]
        self.assertEqual(side["parent_session"], MAIN_SESSION)
        self.assertEqual(side["side_name"], "wt-side")
        self.assertEqual(side["provider"], "claude")
        self.assertIn(NESTED_SIDE, sessions)
        self.assertEqual(sessions[NESTED_SIDE]["parent_session"], WT_SIDE)
        self.assertNotIn(LOST_PARENT_SIDE, sessions)
        existing = sessions[SIDE_SESSION]
        self.assertEqual(existing["parent_session"], MAIN_SESSION)
        self.assertEqual(existing["side_name"], "side")
        self.assertEqual(existing["provider"], "claude")

    def test_external_side_row_owns_labelled_run_and_counts_live(self) -> None:
        from hh_ps.models import Session
        from hh_ps.tree import _rollout_metadata
        row = Session("fake", "fake", "running", "", None, None, None, False, True)
        rollout = self.fx.base / "fake-rollout.jsonl"
        for effort in ({"effort": "high"}, {"reasoning_effort": "high"},
                       {"reasoning": {"effort": "high"}}):
            row.model = row.effort = ""
            rollout.write_text(json.dumps({"timestamp": "2026-11-07T00:00:00Z",
                "ordinal": 12, "type": "session_meta" if "effort" in effort else "turn_context",
                "payload": {"model": "fake-codex", **effort}}) + "\n")
            _rollout_metadata(row, rollout)
            self.assertEqual((row.model, row.effort), ("fake-codex", "high"))
        data = self.json_cli()
        sessions = {item["session_id"]: item for item in data["sessions"]}
        self.assertIn(DSH_SIDE, sessions)
        row = sessions[DSH_SIDE]
        self.assertEqual(row["name"], "dsh-side")
        self.assertEqual(row["status"], "running")
        self.assertTrue(row["live"])
        self.assertEqual(row["context_tokens"], 13000)
        self.assertEqual(row["token_cap"], 40000)
        self.assertTrue(row["started_at"])
        self.assertEqual(row["subagents"], [])
        self.assertEqual([run["run_id"] for run in row["hand_runs"]], ["dsh-side-run"])
        main_runs = [run["run_id"] for run in sessions[MAIN_SESSION]["hand_runs"]]
        self.assertNotIn("dsh-side-run", main_runs)
        self.assertEqual(data["totals"]["live_sessions"],
                         sum(1 for item in data["sessions"] if item["live"]))

    def test_text_indents_side_under_parent_and_groups_unknown(self) -> None:
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        lines = out.splitlines()

        def index(needle: str) -> int:
            return next(i for i, line in enumerate(lines) if needle in line)

        main = index("WP-23b")
        main_run = index("main-run")
        dsh = index("phụ:dsh-side")
        self.assertGreater(dsh, main_run)
        self.assertTrue(lines[dsh].startswith("│ "), lines[dsh])
        wt = index("phụ:wt-side")
        self.assertGreater(wt, main_run)
        self.assertTrue(lines[wt].startswith("│ "), lines[wt])
        nested = index("phụ:nested-side")
        self.assertGreater(nested, wt)
        self.assertTrue(lines[nested].startswith("│ │ "), lines[nested])
        unknown = index("phiên phụ chưa rõ phiên cha")
        self.assertGreater(unknown, nested)
        orphan = index("phụ:mo-coi")
        self.assertGreater(orphan, unknown)
        self.assertLess(orphan, index("Tổng:"))
        self.assertGreater(index("Tổng:"), unknown)

    def test_legacy_state_without_parent_session_is_tolerated(self) -> None:
        sessions = {item["session_id"]: item
                    for item in self.json_cli("--ended")["sessions"]}
        legacy = sessions[NONAME_SESSION]
        self.assertIsNone(legacy["parent_session"])
        self.assertEqual(legacy["side_name"], "legacy-side")
        self.assertEqual(legacy["provider"], "claude")
        self.assertEqual(legacy["token_cap"], 10000)

    def test_watch_one_iteration_draws_nested_tree(self) -> None:
        code, out = self.run_cli("--watch", "2", "--count", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("phụ:dsh-side", out)
        self.assertIn("phiên phụ chưa rõ phiên cha", out)


if __name__ == "__main__":
    unittest.main()


class SideLabelTargetTest(unittest.TestCase):
    def test_run_registered_in_same_second_as_fractional_state_start(self) -> None:
        from hh_ps.models import HandRun, Session
        from hh_ps.tree import _label_target

        session = Session(session_id="s", name="x", status="running", cwd="",
                          context_tokens=None, started_at=None, last_activity=None,
                          is_main=False, live=True)
        run = HandRun(run_id="r", label="side-x", backend="dsh", status="running",
                      started_at=1000.0, ended_at=None, parent_session=None, tokens={},
                      model="", pid=None, child_pid=None, lost=False)
        self.assertIs(_label_target(run, {"side-x": (session, 1000.7)}), session)
        self.assertIsNone(_label_target(run, {"side-x": (session, 1001.2)}))
