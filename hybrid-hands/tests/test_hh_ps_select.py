"""`hh-ps` lists running children, the 3 newest finished ones and a summary."""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))

from hh_ps import cli  # noqa: E402
from hh_ps.constants import FULL_FLAG, RECENT_FINISHED_SHOWN  # noqa: E402
from hh_ps.models import HandRun, Session, Snapshot, Subagent  # noqa: E402
from hh_ps.selection import ChildItem, select_children  # noqa: E402
from hh_ps.textwidth import display_width  # noqa: E402
from hh_ps.text_render import render_text  # noqa: E402
from hh_ps.textwidth import display_width  # noqa: E402

NOW = 1_800_000_000.0
MAX_CHILD_CELLS = 68
FINISHED_OK = 5
FAILED = 2


def _session(sid: str, live: bool = True) -> Session:
    return Session(session_id=sid, name=sid, status="busy" if live else "idle", cwd="",
                   context_tokens=1000, started_at=NOW - 900, last_activity=NOW - 60,
                   is_main=False, live=live)


def _done(index: int) -> Subagent:
    # Minute `index` ago: done-1 is the newest.
    return Subagent(f"a{index}", "t", f"done-{index}", True, False, 1000, 30.0,
                    NOW - 60 * index)


def _failed(index: int) -> HandRun:
    return HandRun(f"r{index}", f"fail-{index}", "dsh", "m", "failed", None,
                   {"output": 10}, NOW - 900, NOW - 60 * index, None, None, False)


def _running() -> HandRun:
    return HandRun("run", "chạy", "dsh", "m", "running", None, {"output": 1},
                   NOW - 120, None, None, None, False)


def _mixed(sid: str) -> Session:
    """5 finished subagents (1..5 min ago), 2 failed runs (2.5, 7 min) and 1 running."""
    session = _session(sid)
    session.subagents.extend(_done(i) for i in range(1, FINISHED_OK + 1))
    session.hand_runs.extend([_failed(2.5), _failed(7), _running()])
    return session


def _render(sessions, full: bool = False) -> list:
    snap = Snapshot(sessions=sessions, orphan_runs=[], since_seconds=3600, cwd="",
                    all_projects=False, main_session_id=None, generated_at=NOW)
    return render_text(snap, full=full).splitlines()


class SelectChildrenTest(unittest.TestCase):
    def test_running_first_then_newest_finished_then_counts(self) -> None:
        items = [ChildItem(f"ok{i}", False, False, NOW - i) for i in range(5)]
        items += [ChildItem("bad", False, True, NOW - 10), ChildItem("run", True, False, None)]
        picked = select_children(items)
        self.assertEqual(picked.shown, ["run", "ok0", "ok1", "ok2"])
        self.assertEqual(picked.summary, "+2 xong · 1 lỗi")
        self.assertEqual(len(select_children(items, full=True).shown), len(items))

    def test_summary_drops_zero_parts(self) -> None:
        only_bad = [ChildItem(i, False, True, NOW - i) for i in range(4)]
        self.assertEqual(select_children(only_bad).summary, "+1 lỗi")
        self.assertEqual(select_children(only_bad[:3]).summary, "")


class TextRuleTest(unittest.TestCase):
    def test_session_rule_and_summary(self) -> None:
        lines = _render([_mixed("s")])
        children = lines[3:-2]
        self.assertIn("chạy", children[0])
        # Newest three by end time: done-1, done-2, fail-2.5 (failed mixes in).
        self.assertIn("done-1", children[1])
        self.assertIn("done-2", children[2])
        self.assertIn("fail-2.5", children[3])
        self.assertEqual(children[4], "  └ +3 xong · 1 lỗi")
        self.assertEqual(len(children), 1 + RECENT_FINISHED_SHOWN + 1)

    def test_full_lists_every_child(self) -> None:
        text = "\n".join(_render([_mixed("s")], full=True))
        for name in [f"done-{i}" for i in range(1, 6)] + ["fail-7", "fail-2.5", "chạy"]:
            self.assertIn(name, text)
        self.assertNotIn("+3 xong", text)

    def test_duration_cell_comes_before_description(self) -> None:
        row = next(line for line in _render([_mixed("s")]) if "done-1" in line)
        self.assertLess(row.index("30s"), row.index(" - "))  # USD unknown
        self.assertLess(row.index(" - "), row.index("done-1"))
        self.assertNotIn("ctx", row)
        self.assertTrue(row.endswith("done-1"))
        failed = next(line for line in _render([_mixed("s")]) if "fail-2.5" in line)
        self.assertGreater(failed.index("failed"), failed.index("fail-2.5"))
        self.assertTrue(all(display_width(line) <= MAX_CHILD_CELLS
                            for line in _render([_mixed("s")])[3:-2]))

    def test_ok_row_has_no_gap_before_description(self) -> None:
        lines = _render([_mixed("s")])
        ok = next(line for line in lines if "done-1" in line)
        self.assertRegex(ok, r" -\s+done-1$")  # USD `-`, empty limit %  # status column sits after it
        failed = next(line for line in lines if "fail-2.5" in line)
        self.assertEqual(failed.index("fail-2.5"), ok.index("done-1"))

    def test_side_sessions_with_different_names_share_time_column(self) -> None:
        parent = _session("cha")
        parent.subagents.append(_done(1))
        sides = []
        for name in ("RV-12b", "RV-10"):
            side = _session(f"phụ-{name}")
            side.parent_session, side.side_name = "cha", name
            sides.append(side)
        lines = _render([parent, *sides])
        rows = [line for line in lines if "phụ:RV" in line]
        self.assertEqual(len(rows), 2)
        # The time cell is right-aligned; the USD cell `-` ends both rows.
        usd = [row.rindex("-") for row in rows]
        time_ends = {display_width(row[:at].rstrip()) for row, at in zip(rows, usd)}
        self.assertEqual(len(time_ends), 1, rows)
        self.assertEqual(len({display_width(row[:at]) for row, at in zip(rows, usd)}), 1, rows)

    def test_side_session_is_a_child_with_its_own_rule(self) -> None:
        parent = _session("cha")
        parent.subagents.extend(_done(i) for i in range(1, 5))
        live_side = _mixed("phụ-sống")
        live_side.parent_session, live_side.side_name = "cha", "sống"
        old_side = _session("phụ-cũ", live=False)  # ended 1 min ago (last_activity)
        old_side.parent_session, old_side.side_name = "cha", "cũ"
        lines = _render([parent, live_side, old_side])
        text = "\n".join(lines)
        self.assertRegex(lines[3], r"^  ├ ● phụ:sống +1p +-$")
        child = next(line for line in lines if "done-1" in line)
        self.assertEqual(lines[3].rindex("-"), child.rindex(" -") + 1)  # shared columns
        self.assertIn("  │ └ +3 xong · 1 lỗi", text)
        # Recent: done-1 (1 min), ended side (1 min, sorted after), done-2; done-3, done-4 fold.
        self.assertIn("○ phụ:cũ", text)
        self.assertNotIn("done-3", text)
        self.assertEqual(lines[-3], "  └ +2 xong")


class FullFlagCliTest(unittest.TestCase):
    def test_full_flag_is_accepted(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main([FULL_FLAG, "--since", "1m", "--cwd", str(TESTS)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
