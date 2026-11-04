"""Text tree and JSON output for hh-ps (no message or prompt content is rendered)."""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, TextIO

from .constants import (
    BRANCH, COLOR_RESET, COLORS, DESCRIPTION_MAX_LEN, ELLIPSIS, ENDED_DOT, LAST_BRANCH,
    LIVE_DOT, MAIN_MARKER, NO_COLOR_ENV, ORPHAN_HEADING, PIPE, RUN_LOST_TEXT,
    RUN_STATE_LOST, RUN_STATE_RUNNING, SCHEMA_VERSION, SPACE, SUBAGENT_SILENT,
)
from .models import HandRun, Session, Snapshot, Subagent
from .timeutil import (
    age_text, duration_text, iso_at, ratio_text, short_path, token_text, truncate,
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


def _session_line(session: Session, color: bool, now: float) -> str:
    status_key = _session_status_key(session)
    dot = LIVE_DOT if session.live else ENDED_DOT
    parts = [f"{_paint(dot, status_key, color)} {session.name}"]
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


def _children(lines: List[str], last: bool) -> List[str]:
    prefix = SPACE if last else PIPE
    out = []
    for index, line in enumerate(lines):
        branch = LAST_BRANCH if index == len(lines) - 1 else BRANCH
        out.append(prefix + branch + line)
    return out


def _session_block(session: Session, last: bool, color: bool, now: float) -> List[str]:
    block = [(LAST_BRANCH if last else BRANCH) + _session_line(session, color, now)]
    children = [_subagent_line(agent, color) for agent in session.subagents]
    children += [_run_line(run, color, now) for run in session.hand_runs]
    block += _children(children, last)
    return block


def _orphan_block(runs: List[HandRun], last: bool, color: bool, now: float) -> List[str]:
    block = [(LAST_BRANCH if last else BRANCH) + ORPHAN_HEADING]
    block += _children([_run_line(run, color, now) for run in runs], last)
    return block


def render_text(snapshot: Snapshot, color: bool = False) -> str:
    total = len(snapshot.sessions) + (1 if snapshot.orphan_runs else 0)
    lines = [f"Phiên Claude ({snapshot.live_sessions} sống / {len(snapshot.sessions)} phiên)"
             f" · since {duration_text(snapshot.since_seconds)}"]
    if not total:
        lines.append("(không có phiên hay lượt hand nào trong khoảng --since)")
    index = 0
    for session in snapshot.sessions:
        index += 1
        lines += _session_block(session, index == total, color, snapshot.generated_at)
    if snapshot.orphan_runs:
        index += 1
        lines += _orphan_block(snapshot.orphan_runs, index == total, color,
                               snapshot.generated_at)
    lines.append("")
    lines.append(f"Tổng: {snapshot.live_sessions} phiên sống, "
                 f"{snapshot.running_subagents} subagent đang chạy, "
                 f"{snapshot.running_hand_runs} hand ngoài đang chạy")
    return "\n".join(lines)


def _hand_run_json(run: HandRun, now: float) -> Dict[str, object]:
    end = run.ended_at if run.ended_at is not None else now
    duration = None if run.started_at is None else max(0.0, end - run.started_at)
    return {
        "run_id": run.run_id,
        "label": run.label,
        "backend": run.backend,
        "model": run.model,
        "status": run.status,
        "state": run.state,
        "tokens": dict(run.tokens),
        "started_at": iso_at(run.started_at),
        "ended_at": iso_at(run.ended_at),
        "duration_seconds": duration,
        "parent_session": run.parent_session,
        "pid": run.pid,
        "child_pid": run.child_pid,
    }


def _subagent_json(agent: Subagent) -> Dict[str, object]:
    status = ("running" if agent.running else
              "silent" if agent.state == SUBAGENT_SILENT else "finished")
    return {
        "agent_id": agent.agent_id,
        "agent_type": agent.agent_type,
        "description": agent.description,
        "status": status,
        "context_tokens": agent.context_tokens,
        "duration_seconds": agent.duration_seconds,
    }


def _session_json(session: Session, now: float) -> Dict[str, object]:
    return {
        "session_id": session.session_id,
        "name": session.name,
        "status": session.status,
        "cwd": session.cwd,
        "context_tokens": session.context_tokens,
        "started_at": iso_at(session.started_at),
        "last_activity": iso_at(session.last_activity),
        "is_main": session.is_main,
        "live": session.live,
        "project_slug": session.project_slug,
        "transcript_path": str(session.transcript_path) if session.transcript_path else None,
        "token_cap": session.token_cap,
        "token_ratio": session.token_ratio,
        "subagents": [_subagent_json(agent) for agent in session.subagents],
        "hand_runs": [_hand_run_json(run, now) for run in session.hand_runs],
    }


def render_json(snapshot: Snapshot) -> Dict[str, object]:
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": iso_at(snapshot.generated_at),
        "since_seconds": snapshot.since_seconds,
        "cwd": snapshot.cwd,
        "all_projects": snapshot.all_projects,
        "main_session_id": snapshot.main_session_id,
        "sessions": [_session_json(session, snapshot.generated_at)
                     for session in snapshot.sessions],
        "orphan_runs": [_hand_run_json(run, snapshot.generated_at)
                        for run in snapshot.orphan_runs],
        "totals": {
            "live_sessions": snapshot.live_sessions,
            "running_subagents": snapshot.running_subagents,
            "running_hand_runs": snapshot.running_hand_runs,
        },
    }
