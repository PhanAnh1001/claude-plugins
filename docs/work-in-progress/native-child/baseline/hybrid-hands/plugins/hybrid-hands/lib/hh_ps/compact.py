"""Shared text rows: kind, full model/effort, elapsed, local completion time, estimated cost and account quota."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from .constants import (
    CHILD_BAD_MARK, CHILD_OK_MARK, CHILD_RUNNING_MARK, DESCRIPTION_MAX_LEN, ENDED_DOT,
    HERE_MARK, KIND_ALIASES, KIND_MAX_LEN, LIVE_DOT, OK_STATUSES, RUN_LOST_TEXT,
    RUN_STATE_LOST, RUN_STATE_RUNNING, SESSION_NAME_MAX_LEN, SIDE_NAME_PREFIX,
    STATUS_ALIASES, SUBAGENT_RUNNING, SUBAGENT_SILENT,
)
from .models import HandRun, Limit, Session, Subagent, Usage
from .table import GROUP_TREE, Cell, Line
from .textwidth import truncate_display
from .timeutil import duration_text, ended_text, percent_text, usd_text

UNKNOWN = "-"
UNKNOWN_PCT = "?"
GPT_PLAN = "GPT"
WEEK_WINDOW = "tuần"
LIMIT_GAP = "   "


def _age(moment: Optional[float], now: float) -> Optional[float]:
    return None if moment is None else max(0.0, now - moment)


def session_name(session: Session) -> str:
    raw = f"{SIDE_NAME_PREFIX}{session.side_name}" if session.side_name else session.name
    return truncate_display(raw or session.session_id[:8], SESSION_NAME_MAX_LEN)


def session_status_key(session: Session) -> str:
    if session.is_main:
        return "main"
    if not session.live:
        return "ended"
    return "busy" if session.status == "busy" else "idle"


def _session_mark(session: Session) -> Cell:
    key = session_status_key(session)
    mark = HERE_MARK if session.is_main else LIVE_DOT if session.live else ENDED_DOT
    return Cell(mark, key)


def elapsed_seconds(start: Optional[float], end: Optional[float], running: bool,
                    now: float) -> Optional[float]:
    if start is None or (end is None and not running):
        return None
    return max(0.0, (end if end is not None else now) - start)


def subagent_duration(agent: Subagent, now: float) -> Optional[float]:
    start = getattr(agent, "started_at", None)
    if start is None:
        return agent.duration_seconds
    return elapsed_seconds(start, agent.ended_at, not agent.finished, now)


def model_effort(row) -> str:
    return f"{getattr(row, 'model', '') or '?'}/{getattr(row, 'effort', '') or '?'}"


def end_cell(end: Optional[float], running: bool, now: float) -> str:
    if running:
        return "đang chạy"
    return datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M") if end is not None else "?"


def usage_cells(usage: Optional[Usage]) -> List[Cell]:
    amount = usage.usd if usage is not None else None
    usd = f"~{usd_text(amount)}" if amount is not None else "~$?"
    five = getattr(usage, "account_5h_pct", None)
    week = getattr(usage, "account_week_pct", None)
    if usage is not None:
        if five is None:
            five = usage.gpt_5h_pct
        if week is None:
            week = usage.gpt_week_pct
    plan = getattr(usage, "account_plan", "") or "TK"
    share = f"{plan} 5h {percent_text(five) or '?'} · tuần {percent_text(week) or '?'}"
    if usage is not None and usage.week_pct is not None:
        share += f" · riêng {percent_text(usage.week_pct, usage.week_pct_estimated)} tuần"
    return [Cell(usd, align_right=True), Cell(share, align_right=True)]


def limit_line(limit: Limit, now: float) -> str:
    """One `Hạn mức` row; GPT is account-only, Claude/Go keep the machine split."""
    reset = ended_text(limit.resets_at, now)
    mark = limit.estimated
    if limit.plan == GPT_PLAN:
        parts = [f"tổng {percent_text(limit.total_pct, mark) or UNKNOWN_PCT}"]
    else:
        parts = [
            f"máy này {percent_text(limit.this_machine_pct, mark) or UNKNOWN_PCT}",
            f"máy khác {percent_text(limit.other_pct, mark) or UNKNOWN_PCT}",
            f"tổng {percent_text(limit.total_pct, mark) or UNKNOWN_PCT}",
        ]
    if reset:
        parts.append(f"reset {reset}")
    return f"{limit.plan} {limit.window}{LIMIT_GAP}{' · '.join(parts)}"


def session_line(session: Session, now: float) -> Line:
    kind = "side session" if session.side_name else "root session"
    duration = elapsed_seconds(session.started_at, session.ended_at, session.live, now)
    cells = [Cell(f"{session_name(session)} ({kind})"),
             Cell(model_effort(session)), Cell(duration_text(duration) or "?", align_right=True),
             Cell(end_cell(session.ended_at, session.live, now)),
             *usage_cells(session.usage), Cell(session.status)]
    return Line("", cells, GROUP_TREE, _session_mark(session))


def side_child_line(session: Session, now: float) -> Line:
    return session_line(session, now)


def child_kind(raw: Optional[str]) -> str:
    kind = raw or UNKNOWN
    return KIND_ALIASES.get(kind, kind)


def bad_status(raw: Optional[str]) -> str:
    """Status text for a child that did not finish ok; empty when ok."""
    status = raw or ""
    if status in OK_STATUSES:
        return ""
    return STATUS_ALIASES.get(status, status)


def _child_line(mark: str, key: str, kind: str, description: str, status: str,
                duration: Optional[str], end: Optional[str],
                usage: Optional[Usage], model: str) -> Line:
    cells = [Cell(child_kind(kind)), Cell(model), Cell(duration or "?", align_right=True), Cell(end),
             *usage_cells(usage),
             Cell(truncate_display(description or "", DESCRIPTION_MAX_LEN)),
             Cell(status, key)]
    return Line("", cells, GROUP_TREE, Cell(mark, key))


def subagent_line(agent: Subagent, now: float) -> Line:
    if agent.state == SUBAGENT_RUNNING:
        mark, key, status = CHILD_RUNNING_MARK, "running", ""
    elif agent.state == SUBAGENT_SILENT:
        mark, key, status = CHILD_RUNNING_MARK, "lost", SUBAGENT_SILENT
    else:
        mark, key, status = CHILD_OK_MARK, "finished", ""
    return _child_line(mark, key, agent.agent_type, agent.description, status,
                       duration_text(subagent_duration(agent, now)),
                       end_cell(agent.ended_at, not agent.finished, now), agent.usage, model_effort(agent))


def _run_mark(run: HandRun) -> tuple:
    if run.state == RUN_STATE_LOST:
        return CHILD_BAD_MARK, "lost", RUN_LOST_TEXT
    if run.state == RUN_STATE_RUNNING:
        return CHILD_RUNNING_MARK, "running", ""
    status = bad_status(run.status or UNKNOWN)
    return (CHILD_BAD_MARK, "lost", status) if status else (CHILD_OK_MARK, "finished", "")


def run_is_bad(run: HandRun) -> bool:
    return _run_mark(run)[0] == CHILD_BAD_MARK


def run_line(run: HandRun, now: float) -> Line:
    mark, key, status = _run_mark(run)
    duration = duration_text(elapsed_seconds(run.started_at, run.ended_at, run.running, now))
    usage = run.usage
    return _child_line(mark, key, run.backend, run.label or UNKNOWN, status,
                       duration, end_cell(run.end_moment, run.running, now), usage, model_effort(run))
