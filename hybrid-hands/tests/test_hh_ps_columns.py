"""`hh-ps` text tree aligns columns by terminal display width."""
from __future__ import annotations

import re
import sys
import unicodedata
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))

from hh_ps.models import HandRun, Session, Snapshot, Subagent, Usage  # noqa: E402
from hh_ps.text_render import render_text  # noqa: E402
from hh_ps.compact import bad_status, child_kind  # noqa: E402
from hh_ps.textwidth import display_width, pad_left, pad_right  # noqa: E402
from hh_ps.timeutil import token_text  # noqa: E402

NOW = 1_800_000_000.0
VIETNAMESE = "phân tích đo lặp"
# Targets from the hh-ps README after the USD/% cells: still pane-sized.
MAX_CHILD_CELLS = 100
MAX_SESSION_CELLS = 92
# Every test agent costs this much, so its USD text marks the USD column.
AGENT_USD = 0.02
USD_MARK = "$0.02"
LONG_TEXT = "Statusline decimal estimates + Go per session split và đo lặp lại"


def _agent(description: str, finished: bool) -> Subagent:
    return Subagent("a", "hybrid-hands:hand", description, finished, False, 1000,
                    60.0, NOW - 5, Usage(usd=AGENT_USD))


def _session(name: str, agents) -> Session:
    session = Session(session_id=name, name=name, status="busy", cwd="",
                      context_tokens=None, started_at=None, last_activity=NOW,
                      is_main=False, live=True)
    session.subagents.extend(agents)
    return session


def _render(sessions) -> list:
    snap = Snapshot(sessions=sessions, orphan_runs=[], since_seconds=3600, cwd="",
                    all_projects=False, main_session_id=None, generated_at=NOW)
    return render_text(snap).splitlines()


def _column_start(line: str, token: str) -> int:
    return display_width(line[:line.index(token)])


class DisplayWidthTest(unittest.TestCase):
    def test_vietnamese_nfc_and_nfd_have_same_width(self) -> None:
        nfd = unicodedata.normalize("NFD", VIETNAMESE)
        self.assertNotEqual(len(nfd), len(VIETNAMESE))
        self.assertEqual(display_width(VIETNAMESE), len(VIETNAMESE))
        self.assertEqual(display_width(nfd), len(VIETNAMESE))

    def test_wide_characters_and_ansi(self) -> None:
        self.assertEqual(display_width("漢字"), 4)
        self.assertEqual(display_width("\033[32mbusy\033[0m"), 4)

    def test_pad_uses_display_width(self) -> None:
        nfd = unicodedata.normalize("NFD", "đã")
        self.assertEqual(display_width(pad_right(nfd, 5)), 5)
        self.assertEqual(pad_left("4p", 4), "  4p")


class ColumnAlignmentTest(unittest.TestCase):
    def test_size_column_lines_up_for_short_and_long_descriptions(self) -> None:
        lines = _render([_session("s", [_agent("ngắn", True),
                                        _agent("một mô tả dài hơn nhiều", False)])])
        rows = [line for line in lines if USD_MARK in line]
        self.assertEqual(_column_start(rows[0], USD_MARK), _column_start(rows[1], USD_MARK))

    def test_nfd_description_aligns_with_nfc(self) -> None:
        nfd = unicodedata.normalize("NFD", VIETNAMESE)
        lines = _render([_session("s", [_agent(VIETNAMESE, True), _agent(nfd, False)])])
        rows = [line for line in lines if USD_MARK in line]
        self.assertEqual(_column_start(rows[0], USD_MARK), _column_start(rows[1], USD_MARK))

    def test_children_at_different_depths_line_up(self) -> None:
        parent = _session("cha", [_agent("x", True)])
        side = _session("phụ", [_agent("y", True)])
        side.parent_session, side.side_name, side.provider = "cha", "phụ", "claude"
        lines = [line for line in _render([parent, side]) if USD_MARK in line]
        self.assertEqual(len(lines), 2)
        self.assertEqual(_column_start(lines[0], USD_MARK), _column_start(lines[1], USD_MARK))

    def test_session_status_column_lines_up(self) -> None:
        lines = _render([_session("a", []), _session("tên-dài-hơn", [])])
        rows = [line for line in lines if "busy" in line]
        self.assertEqual(_column_start(rows[0], "busy"), _column_start(rows[1], "busy"))

    def test_session_status_uses_the_child_end_column(self) -> None:
        main = _session("cha", [_agent("con", True)])
        lines = _render([main])
        session = next(line for line in lines if "busy" in line)
        child = next(line for line in lines if USD_MARK in line)
        end = re.search(r"\d\d:\d\d", child).group(0)
        self.assertEqual(_column_start(session, "busy"), _column_start(child, end))

    def test_usd_column_lines_up_for_session_side_and_children(self) -> None:
        main = _session("cha", [_agent("con", True)])
        main.usage = Usage(usd=AGENT_USD)
        main.hand_runs.append(_run("lượt", main.session_id, lost=True))
        side = _session("phụ", [_agent("cháu", True)])
        side.parent_session, side.side_name, side.provider = "cha", "phụ", "claude"
        side.usage = Usage(usd=AGENT_USD)
        lines = _render([main, side])
        usd_rows = [line for line in lines if "$0." in line]
        # Every USD text here is `$0.xx`, so equal starts mean equal right edges.
        starts = {_column_start(line, "$0.") for line in usd_rows}
        self.assertEqual(len(usd_rows), 5, "\n".join(lines))
        self.assertEqual(len(starts), 1, "\n".join(lines))
        self.assertNotIn("ctx ", "\n".join(lines))


class CompactFormatTest(unittest.TestCase):
    def test_token_text_compact(self) -> None:
        cases = {950: "950", 6400: "6.4k", 46_300: "46k", 95_000: "95k",
                 1_234_000: "1.2M", 999_700: "1M"}
        for count, text in cases.items():
            self.assertEqual(token_text(count), text, count)

    def test_kind_and_status_aliases(self) -> None:
        self.assertEqual(child_kind("hybrid-hands:hand"), "hand")
        self.assertEqual(child_kind("opencode"), "oc")
        self.assertEqual(child_kind("general-purpose"), "general…")
        self.assertEqual(bad_status("quota_exhausted"), "quota")
        self.assertEqual(bad_status("ok"), "")


def _run(label: str, parent: str, lost: bool, status: str = "running") -> HandRun:
    tokens = {"input": 6_400_000, "cached_input": 6_200_000, "output": 46_300}
    ended = None if status == "running" else NOW - 60
    return HandRun("r", label, "opencode", "m", status, parent, tokens, NOW - 3000,
                   ended, 1, None, lost, week_limit_usd=64.0)


class LineWidthTest(unittest.TestCase):
    def test_nested_tree_fits_narrow_pane(self) -> None:
        main = _session("ai-luxian-06-một-tên-phiên-rất-dài", [_agent(LONG_TEXT, True)])
        main.context_tokens, main.is_main = 157_200, True
        main.hand_runs.append(_run(LONG_TEXT, main.session_id, lost=True))
        side = _session("side", [_agent(LONG_TEXT, False)])
        side.parent_session, side.side_name, side.provider = main.session_id, "RV-12", "claude"
        side.hand_runs.append(_run(LONG_TEXT, side.session_id, False, "quota_exhausted"))
        nested = _session("nested", [_agent(LONG_TEXT, True)])
        nested.parent_session, nested.side_name = side.session_id, "lồng-sâu"
        lines = _render([main, side, nested])
        text = "\n".join(lines)
        self.assertIn("▶ ai-luxian-06-mộ…", text)
        self.assertIn("$0.15  0.2% tuần", text)  # Go hand: USD and weekly %, no tokens
        self.assertNotIn("out ", text)
        self.assertIn("quota", text)
        self.assertIn("mất", text)
        self.assertIn("  │ ├ ● phụ:lồng-sâu", text)  # nested two levels
        self.assertNotIn("kết thúc", text)
        children = [line for line in lines if "$0." in line and ("✓" in line or "✗" in line)]
        sessions = [line for line in lines[2:] if "● " in line or "▶ ai" in line]
        self.assertLessEqual(max(display_width(line) for line in children),
                             MAX_CHILD_CELLS, text)
        self.assertLessEqual(max(display_width(line) for line in sessions),
                             MAX_SESSION_CELLS, text)


if __name__ == "__main__":
    unittest.main()
