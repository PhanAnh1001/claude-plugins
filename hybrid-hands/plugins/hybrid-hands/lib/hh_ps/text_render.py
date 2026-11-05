"""Text tree for `hh-ps` (no message or prompt content is rendered)."""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, TextIO

from .constants import (
    BRANCH, COLORS, COLOR_RESET, DESCRIPTION_MAX_LEN, ENDED_DOT, LAST_BRANCH, LIVE_DOT,
    MAIN_MARKER, NO_COLOR_ENV, ORPHAN_HEADING, PIPE, RUN_LOST_TEXT, RUN_STATE_LOST,
    RUN_STATE_RUNNING, SIDE_SESSION_LABEL, SIDE_UNKNOWN_HEADING, SPACE, SUBAGENT_SILENT,
)
from .models import HandRun, Session, Snapshot, Subagent
from .timeutil import (
    age_text, duration_text, ratio_text, short_path, token_text, truncate,
)

SEPARATOR = " · "
UNKNOWN = "-"


def color_enabled(stream: Optional[TextIO] = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get(NO_COLOR_ENV) is not None:
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _paint(text: str, key: str, color: bool) -> str:
    if not color or key not in COLORS:
        return text
    return f"{COLORS[key]}{text}{COLOR_RESET}"


def _session_status_key(session: Session) -> str:
    if not session.live:
        return "ended"
    return "busy" if session.status == "busy" else "idle"


def _token_label(session: Session) -> str:
    context = token_text(session.context_tokens)
    cap = token_text(session.token_cap)
    if cap and context:
        ratio = ratio_text(session.context_tokens, session.token_cap)
        return f"ctx {context}/{cap}" + (f" ({ratio})" if ratio else "")
    if cap:
        return f"ctx {UNKNOWN}/{cap}"
    if context:
        return f"ctx {context}"
    return ""


def _side_label(session: Session) -> str:
    if not session.side_name:
        return ""
    return f"{SIDE_SESSION_LABEL} {session.side_name} [{session.provider}]"


def _session_line(session: Session, color: bool, now: float) -> str:
    status_key = _session_status_key(session)
    dot = LIVE_DOT if session.live else ENDED_DOT
    parts = [f"{_paint(dot, status_key, color)} {session.name}"]
    side = _side_label(session)
    if side:
        parts.append(side)
    if session.is_main:
        parts.append(_paint(MAIN_MARKER, "main", color))
    parts.append(_paint(session.status, status_key, color))
    cwd = short_path(session.cwd)
    if cwd:
        parts.append(cwd)
    tokens = _token_label(session)
    if tokens:
        parts.append(tokens)
    started = age_text(_age(session.started_at, now))
    if started:
        parts.append(f"bắt đầu {started}")
    active = age_text(_age(session.last_activity, now))
    if active:
        parts.append(f"hoạt động {active}")
    return SEPARATOR.join(parts)


def _age(moment: Optional[float], now: float) -> Optional[float]:
    if moment is None:
        return None
    return max(0.0, now - moment)


def _subagent_line(agent: Subagent, color: bool) -> str:
    parts = []
    if agent.agent_type:
        parts.append(agent.agent_type)
    description = truncate(agent.description, DESCRIPTION_MAX_LEN)
    if description:
        parts.append(description)
    key = "running" if agent.running else "finished"
    parts.append(_paint(agent.state, key, color))
    context = token_text(agent.context_tokens)
    if context:
        parts.append(f"ctx {context}")
    duration = duration_text(agent.duration_seconds)
    if duration:
        parts.append(duration)
    return SEPARATOR.join(parts)


def _run_line(run: HandRun, color: bool, now: float) -> str:
    parts = [run.backend or UNKNOWN, run.label or UNKNOWN]
    if run.state == RUN_STATE_LOST:
        parts.append(_paint(RUN_LOST_TEXT, "lost", color))
    elif run.state == RUN_STATE_RUNNING:
        parts.append(_paint("đang chạy", "running", color))
    else:
        parts.append(run.status or UNKNOWN)
    output = ", ".join(f"{label} {token_text(run.tokens.get(key)) or 0}"
                       for key, label in (("input", "in"),
                                          ("cached_input", "cached"),
                                          ("output", "out")))
    parts.append(output)
    end = run.ended_at if run.ended_at is not None else now
    duration = duration_text(None if run.started_at is None else end - run.started_at)
    if duration:
        parts.append(duration)
    return SEPARATOR.join(parts)


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


def _session_block(session: Session, last: bool, children: Dict[str, List[Session]],
                   color: bool, now: float) -> List[str]:
    block = [(LAST_BRANCH if last else BRANCH) + _session_line(session, color, now)]
    lines = [_subagent_line(agent, color) for agent in session.subagents]
    lines += [_run_line(run, color, now) for run in session.hand_runs]
    nested = children.get(session.session_id, [])
    prefix = SPACE if last else PIPE
    total = len(lines) + len(nested)
    position = 0
    for text in lines:
        position += 1
        branch = LAST_BRANCH if position == total else BRANCH
        block.append(prefix + branch + text)
    for child in nested:
        position += 1
        child_last = position == total
        for line in _session_block(child, child_last, children, color, now):
            block.append(prefix + line)
    return block


def _unknown_block(unknown: List[Session], last: bool,
                   children: Dict[str, List[Session]], color: bool,
                   now: float) -> List[str]:
    block = [(LAST_BRANCH if last else BRANCH) + SIDE_UNKNOWN_HEADING]
    prefix = SPACE if last else PIPE
    for index, session in enumerate(unknown):
        child_last = index == len(unknown) - 1
        for line in _session_block(session, child_last, children, color, now):
            block.append(prefix + line)
    return block


def _orphan_block(runs: List[HandRun], last: bool, color: bool, now: float) -> List[str]:
    block = [(LAST_BRANCH if last else BRANCH) + ORPHAN_HEADING]
    block += _children([_run_line(run, color, now) for run in runs], last)
    return block


def _children(lines: List[str], last: bool) -> List[str]:
    prefix = SPACE if last else PIPE
    out = []
    for index, line in enumerate(lines):
        branch = LAST_BRANCH if index == len(lines) - 1 else BRANCH
        out.append(prefix + branch + line)
    return out


def render_text(snapshot: Snapshot, color: bool = False) -> str:
    roots, unknown, children = _partition(snapshot.sessions)
    total = len(roots) + (1 if unknown else 0) + (1 if snapshot.orphan_runs else 0)
    lines = [f"Phiên Claude ({snapshot.live_sessions} sống / {len(snapshot.sessions)} phiên)"
             f" · since {duration_text(snapshot.since_seconds)}"]
    if not total:
        lines.append("(không có phiên hay lượt hand nào trong khoảng --since)")
    index = 0
    for session in roots:
        index += 1
        lines += _session_block(session, index == total, children, color,
                                snapshot.generated_at)
    if unknown:
        index += 1
        lines += _unknown_block(unknown, index == total, children, color,
                                snapshot.generated_at)
    if snapshot.orphan_runs:
        index += 1
        lines += _orphan_block(snapshot.orphan_runs, index == total, color,
                               snapshot.generated_at)
    lines.append("")
    lines.append(f"Tổng: {snapshot.live_sessions} phiên sống, "
                 f"{snapshot.running_subagents} subagent đang chạy, "
                 f"{snapshot.running_hand_runs} hand ngoài đang chạy")
    return "\n".join(lines)
