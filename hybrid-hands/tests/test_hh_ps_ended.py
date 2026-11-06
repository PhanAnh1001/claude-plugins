"""`hh-ps` default view hides ended trees; end times in text and JSON."""
from __future__ import annotations

import datetime as dt
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

from fixture import HhFixture, MAIN_SESSION  # noqa: E402
from hh_ps import cli  # noqa: E402
from hh_ps.models import HandRun, Session, Snapshot, Subagent  # noqa: E402
from hh_ps.text_render import render_text  # noqa: E402
from hh_ps.timeutil import ended_text  # noqa: E402
from hh_ps.visibility import hide_ended_trees  # noqa: E402

NOW = dt.datetime(2026, 11, 6, 15, 30).timestamp()
SAME_DAY_END = dt.datetime(2026, 11, 6, 9, 5).timestamp()
OTHER_DAY_END = dt.datetime(2026, 11, 4, 23, 50).timestamp()


def _session(sid: str, live: bool, parent: str = None, side: str = None,
             last: float = SAME_DAY_END) -> Session:
    return Session(session_id=sid, name=sid, status="idle" if live else "đã kết thúc",
                   cwd="", context_tokens=None, started_at=None, last_activity=last,
                   is_main=False, live=live, parent_session=parent, side_name=side)


def _run(running: bool, ended: float = None) -> HandRun:
    return HandRun(run_id="r", label="lbl", backend="dsh", model="",
                   status="running" if running else "ok", parent_session=None,
                   tokens={}, started_at=NOW - 60, ended_at=ended, pid=None,
                   child_pid=None, lost=False)


def _snapshot(sessions) -> Snapshot:
    return Snapshot(sessions=sessions, orphan_runs=[], since_seconds=3600, cwd="",
                    all_projects=False, main_session_id=None, generated_at=NOW)


class EndedTextTest(unittest.TestCase):
    def test_same_day_and_other_day(self) -> None:
        self.assertEqual(ended_text(SAME_DAY_END, NOW), "09:05")
        self.assertEqual(ended_text(OTHER_DAY_END, NOW), "04/11 23:50")
        self.assertIsNone(ended_text(None, NOW))


class HideEndedTreesTest(unittest.TestCase):
    def test_dead_tree_hidden_and_counted(self) -> None:
        snap = hide_ended_trees(_snapshot([
            _session("live", True), _session("dead", False),
            _session("dead-side", False, parent="dead", side="x")]))
        self.assertEqual([s.session_id for s in snap.sessions], ["live"])
        self.assertEqual(snap.hidden_ended_sessions, 2)
        out = render_text(snap)
        self.assertIn("(1 sống, ẩn 2 đã kết thúc: --ended để xem)", out)
        self.assertIn("Tổng: 1 phiên sống", out)

    def test_ended_side_under_live_main_kept_with_end_time(self) -> None:
        snap = hide_ended_trees(_snapshot([
            _session("main", True), _session("side", False, parent="main", side="s",
                                             last=OTHER_DAY_END)]))
        self.assertEqual(snap.hidden_ended_sessions, 0)
        lines = render_text(snap).splitlines()
        side = next(line for line in lines if "○ phụ:s" in line)
        self.assertIn("04/11 23:50  -|-|-|-", side)
        main = next(line for line in lines if "● main" in line)
        self.assertNotRegex(main, r"\d\d:\d\d")  # no end time on a live session

    def test_dead_tree_with_running_work_kept(self) -> None:
        with_run = _session("dead-run", False)
        with_run.hand_runs.append(_run(True))
        with_agent = _session("dead-agent", False)
        with_agent.subagents.append(Subagent("a", "t", "d", False, False, None, None, NOW))
        live_child = _session("dead-parent", False)
        snap = hide_ended_trees(_snapshot([
            with_run, with_agent, live_child,
            _session("live-side", True, parent="dead-parent", side="y")]))
        self.assertEqual(len(snap.sessions), 4)
        self.assertEqual(snap.hidden_ended_sessions, 0)

    def test_end_times_on_finished_work_only(self) -> None:
        main = _session("main", True)
        main.subagents.append(Subagent("a", "t", "done", True, False, None, 5.0,
                                       SAME_DAY_END))
        main.subagents.append(Subagent("b", "t", "busy", False, False, None, 5.0, NOW))
        main.hand_runs.append(_run(False, ended=OTHER_DAY_END))
        main.hand_runs.append(_run(True))
        lines = render_text(_snapshot([main])).splitlines()
        self.assertIn("  09:05  ", next(l for l in lines if "done" in l))
        busy = next(l for l in lines if "busy" in l and "lbl" not in l and "●" not in l)
        self.assertNotRegex(busy, r"\d\d:\d\d")
        runs = sorted((l for l in lines if "lbl" in l), key=lambda l: "▶" in l)
        self.assertIn("04/11 23:50", runs[0])
        self.assertNotRegex(runs[1], r"\d\d:\d\d")


class EndedCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = HhFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str) -> str:
        out = io.StringIO()
        with self.fx.env(), redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.fx.project)])
        self.assertEqual(code, 0, out.getvalue())
        return out.getvalue()

    def test_default_hides_ended_and_flag_restores(self) -> None:
        default = self.run_cli()
        self.assertNotIn("ended-name", default)
        self.assertIn("đã kết thúc: --ended để xem", default)
        full = self.run_cli("--ended")
        self.assertIn("ended-name", full)
        self.assertRegex(full.split("ended-name", 1)[1].splitlines()[0], r"\d\d:\d\d")

    def test_json_has_ended_at_and_hidden_count(self) -> None:
        data = json.loads(self.run_cli("--json"))
        self.assertGreater(data["hidden_ended_sessions"], 0)
        main = {s["session_id"]: s for s in data["sessions"]}[MAIN_SESSION]
        self.assertIsNone(main["ended_at"])
        states = {a["status"]: a["ended_at"] for a in main["subagents"]}
        self.assertIsNone(states["running"])
        self.assertTrue(states["finished"])
        self.assertTrue(all("ended_at" in run for run in main["hand_runs"]))
        full = json.loads(self.run_cli("--json", "--ended"))
        self.assertEqual(full["hidden_ended_sessions"], 0)
        ended = [s for s in full["sessions"] if not s["live"]]
        self.assertTrue(ended and all(s["ended_at"] for s in ended))


if __name__ == "__main__":
    unittest.main()
