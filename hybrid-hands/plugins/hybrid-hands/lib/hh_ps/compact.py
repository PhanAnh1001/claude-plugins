"""Compact row layout shared by the `hh-ps` text tree and hh-tree-pane.

Session, side-session and child rows share one column table, so the USD and
limit cells start at the same display column at every depth:
Session: `<mark> <name>  <quiet | end>  <status>  <usd>  <limit %>`.
Child:   `<mark> <kind>  <duration>  [<end>]  <usd>  <limit %>  <description>  [<bad status>]`.
Side session listed as a child: `<mark> phụ:<name>  <quiet | duration>  [<end>]  <usd>  <limit %>  [<ai title>]`.
No token count is shown (not even `ctx`); USD and limit % are right-aligned, and a row with no
known limit share leaves the % cell empty. Codex rows print `~$USD` and an account
sample as `GPT 5h X% · tuần Y%`, never the older Claude/Go `week_pct`. The session status
takes the child end-time column (empty when ended). The bad status follows the
description: it is empty on most rows, so a column before the description would
leave a gap on every ok row. hh-tree-pane (hooks/tree.ts) mirrors these rules;
change both together.
"""
from __future__ import annotations

from typing import List, Optional

from .constants import (
    CHILD_BAD_MARK, CHILD_OK_MARK, CHILD_RUNNING_MARK, DESCRIPTION_MAX_LEN, ENDED_DOT,
    HERE_MARK, KIND_ALIASES, KIND_MAX_LEN, LIVE_DOT, OK_STATUSES, RUN_LOST_TEXT,
    RUN_STATE_LOST, RUN_STATE_RUNNING, SESSION_NAME_MAX_LEN, SIDE_NAME_PREFIX,
    STATUS_ALIASES, SUBAGENT_RUNNING, SUBAGENT_SILENT,
)
from .models import HandRun, Limit, Session, Subagent, Usage
from .pricing import hand_usage
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


def _usd_cell(usage: Optional[Usage]) -> str:
    amount = usage.usd if usage is not None else None
    text = usd_text(amount)
    if text:
        return f"~{text}" if usage is not None and usage.usd_estimated else text
    # Codex knows the row but not a complete price: "?" beats inventing $0.
    return UNKNOWN_PCT if usage is not None and usage.usd_estimated else UNKNOWN


def _gpt_share(usage: Optional[Usage]) -> str:
    if usage is None or (usage.gpt_5h_pct is None and usage.gpt_week_pct is None):
        return ""
    windows = []
    if usage.gpt_5h_pct is not None:
        windows.append(f"5h {percent_text(usage.gpt_5h_pct)}")
    if usage.gpt_week_pct is not None:
        windows.append(f"{WEEK_WINDOW} {percent_text(usage.gpt_week_pct)}")
    return f"GPT {' · '.join(windows)}"


def usage_cells(usage: Optional[Usage]) -> List[Cell]:
    """The right-aligned USD cell and the weekly/GPT-% cell (empty when unknown)."""
    gpt = _gpt_share(usage)
    if gpt:
        share_text = gpt
    else:
        share = usage.week_pct if usage is not None else None
        estimated = usage.week_pct_estimated if usage is not None else False
        week = percent_text(share, estimated)
        share_text = f"{week} {WEEK_WINDOW}" if week else ""
    return [Cell(_usd_cell(usage), align_right=True),
            Cell(share_text, align_right=True)]


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
    live = session.live
    time_text = (duration_text(_age(session.last_activity, now)) if live
                 else ended_text(session.ended_at, now))
    mark = _session_mark(session)
    cells = [
        Cell(session_name(session)),
        Cell(time_text, align_right=True),
        Cell(session.status if live else "", mark.color_key),
        *usage_cells(session.usage),
    ]
    return Line("", cells, GROUP_TREE, mark)


def side_child_line(session: Session, now: float) -> Line:
    """A side session listed among its parent's children (shared tree columns)."""
    if session.live:
        time_text = duration_text(_age(session.last_activity, now))
    elif session.started_at is not None and session.ended_at is not None:
        time_text = duration_text(max(0.0, session.ended_at - session.started_at))
    else:
        time_text = ""
    cells = [Cell(session_name(session)), Cell(time_text, align_right=True),
             Cell(ended_text(session.ended_at, now)),
             *usage_cells(session.usage),
             Cell(truncate_display(session.ai_title or "", DESCRIPTION_MAX_LEN))]
    return Line("", cells, GROUP_TREE, _session_mark(session))


def child_kind(raw: Optional[str]) -> str:
    kind = raw or UNKNOWN
    return truncate_display(KIND_ALIASES.get(kind, kind), KIND_MAX_LEN)


def bad_status(raw: Optional[str]) -> str:
    """Status text for a child that did not finish ok; empty when ok."""
    status = raw or ""
    if status in OK_STATUSES:
        return ""
    return STATUS_ALIASES.get(status, status)


def _child_line(mark: str, key: str, kind: str, description: str, status: str,
                duration: Optional[str], end: Optional[str],
                usage: Optional[Usage]) -> Line:
    cells = [Cell(child_kind(kind)), Cell(duration, align_right=True), Cell(end),
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
                       duration_text(agent.duration_seconds),
                       ended_text(agent.ended_at, now), agent.usage)


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
    end = run.ended_at if run.ended_at is not None else now
    duration = duration_text(None if run.started_at is None else end - run.started_at)
    usage = run.usage
    if usage is None:
        usage = hand_usage(run.tokens, run.backend, run.week_limit_usd,
                           run.week_pct_estimated)
    return _child_line(mark, key, run.backend, run.label or UNKNOWN, status,
                       duration, ended_text(run.end_moment, now), usage)
