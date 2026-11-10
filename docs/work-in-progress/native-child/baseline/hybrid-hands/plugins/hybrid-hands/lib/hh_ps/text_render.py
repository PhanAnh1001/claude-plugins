"""Text tree for `hh-ps` (no message or prompt content is rendered)."""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, TextIO

from .compact import (limit_line, run_is_bad, run_line, session_line, side_child_line,
                      subagent_line)
from .constants import (
    BRANCH, COLORS, COLOR_RESET, ENDED_FLAG, LAST_BRANCH, LEGEND, NO_COLOR_ENV,
    ORPHAN_HEADING, PIPE, SIDE_UNKNOWN_HEADING, SPACE,
)
from .table import Cell, Line, render_lines
from .models import HandRun, Session, Snapshot
from .selection import ChildItem, select_children
from .timeutil import duration_text


def color_enabled(stream: Optional[TextIO] = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get(NO_COLOR_ENV) is not None:
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _paint(text: str, key: Optional[str], color: bool) -> str:
    if not color or key not in COLORS:
        return text
    return f"{COLORS[key]}{text}{COLOR_RESET}"


def _partition(sessions: List[Session]):
    by_id = {session.session_id: session for session in sessions}
    children: Dict[str, List[Session]] = {}
    roots: List[Session] = []
    unknown: List[Session] = []
    for session in sessions:
        parent = by_id.get(session.parent_session) if session.parent_session else None
        if parent is not None:
            children.setdefault(parent.session_id, []).append(session)
        elif session.side_name:
            unknown.append(session)
        else:
            roots.append(session)
    return roots, unknown, children


def _branch(last: bool) -> str:
    return LAST_BRANCH if last else BRANCH


def _heading(text: str, last: bool) -> Line:
    return Line(_branch(last), [Cell(text)])


def _child_items(session: Session, children: Dict[str, List[Session]],
                 now: float) -> List[ChildItem]:
    """Each child as (running?, failed?, end) with a builder of its rows."""
    items: List[ChildItem] = [
        ChildItem([subagent_line(agent, now)], not agent.finished, False, agent.ended_at)
        for agent in session.subagents]
    items += [ChildItem([run_line(run, now)], run.running, run_is_bad(run), run.end_moment)
              for run in session.hand_runs]
    items += [ChildItem(side, side.live, False, side.ended_at)
              for side in children.get(session.session_id, [])]
    return items


def _children(session: Session, children: Dict[str, List[Session]], now: float,
              full: bool) -> List[Line]:
    selection = select_children(_child_items(session, children, now), full)
    entries: List[object] = list(selection.shown)
    if selection.summary:
        entries.append([Line("", [Cell(selection.summary)])])
    lines: List[Line] = []
    for index, entry in enumerate(entries):
        branch = _branch(index == len(entries) - 1)
        if isinstance(entry, Session):
            lines += _side_block(entry, branch, children, now, full)
        else:
            lines += [line.nested(branch) for line in entry]
    return lines


def _side_block(side: Session, branch: str, children: Dict[str, List[Session]],
                now: float, full: bool) -> List[Line]:
    inner = SPACE if branch == LAST_BRANCH else PIPE
    block = [side_child_line(side, now).nested(branch)]
    return block + [line.nested(inner) for line in _children(side, children, now, full)]


def _session_block(session: Session, last: bool, children: Dict[str, List[Session]],
                   now: float, full: bool) -> List[Line]:
    prefix = SPACE if last else PIPE
    block = [session_line(session, now).nested(_branch(last))]
    return block + [line.nested(prefix) for line in _children(session, children, now, full)]


def _unknown_block(unknown: List[Session], last: bool,
                   children: Dict[str, List[Session]], now: float,
                   full: bool) -> List[Line]:
    block = [_heading(SIDE_UNKNOWN_HEADING, last)]
    prefix = SPACE if last else PIPE
    for index, session in enumerate(unknown):
        child_last = index == len(unknown) - 1
        for line in _session_block(session, child_last, children, now, full):
            block.append(line.nested(prefix))
    return block


def _orphan_block(runs: List[HandRun], last: bool, now: float) -> List[Line]:
    prefix = SPACE if last else PIPE
    block = [_heading(ORPHAN_HEADING, last)]
    for index, run in enumerate(runs):
        block.append(run_line(run, now).nested(prefix + _branch(index == len(runs) - 1)))
    return block


def _header_counts(snapshot: Snapshot) -> str:
    hidden = snapshot.hidden_ended_sessions
    if hidden:
        return (f"{snapshot.live_sessions} sống, ẩn {hidden} đã kết thúc: "
                f"{ENDED_FLAG} để xem")
    return f"{snapshot.live_sessions} sống / {len(snapshot.sessions)} phiên"


def render_text(snapshot: Snapshot, color: bool = False, full: bool = False) -> str:
    """List all rows in the snapshot; `full` remains a compatibility argument."""
    roots, unknown, children = _partition(snapshot.sessions)
    total = len(roots) + (1 if unknown else 0) + (1 if snapshot.orphan_runs else 0)
    now = snapshot.generated_at
    header = [f"Phiên Claude ({_header_counts(snapshot)})"
              f" · since {duration_text(snapshot.since_seconds)}", LEGEND]
    if snapshot.limits:
        header.append("Hạn mức")
        header.extend(limit_line(limit, now) for limit in snapshot.limits
                      if limit.plan != "GPT" or limit.total_pct is not None)
    if not total:
        header.append("(không có phiên hay lượt hand nào trong khoảng --since)")
    tree: List[Line] = []
    index = 0
    for session in roots:
        index += 1
        tree += _session_block(session, index == total, children, now, full)
    if unknown:
        index += 1
        tree += _unknown_block(unknown, index == total, children, now, full)
    if snapshot.orphan_runs:
        index += 1
        tree += _orphan_block(snapshot.orphan_runs, index == total, now)
    header.append("LOẠI / TÊN  MODEL/EFFORT  THỜI GIAN  KẾT THÚC (local)  USD  TÀI KHOẢN 5h / tuần")
    lines = header + render_lines(tree, lambda text, key: _paint(text, key, color))
    lines.append("")
    lines.append(f"Tổng: {snapshot.live_sessions} phiên sống, "
                 f"{snapshot.running_subagents} subagent đang chạy, "
                 f"{snapshot.running_hand_runs} hand ngoài đang chạy")
    return "\n".join(lines)
