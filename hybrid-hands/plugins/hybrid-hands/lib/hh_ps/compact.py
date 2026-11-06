"""Compact row layout shared by the `hh-ps` text tree and hh-tree-pane.

Session, side-session and child rows share one column table, so the token block
and the size cell (`ctx`/`out`) start at the same display column at every depth:
Session: `<mark> <name>  <quiet | end>  <status>  <tokens>  <usd>  ctx <N>`.
Child:   `<mark> <kind>  <duration>  [<end>]  <tokens>  <usd>  <size>  <description>  [<bad status>]`.
Side session listed as a child: `<mark> phụ:<name>  <quiet | duration>  [<end>]  <tokens>  <usd>  ctx <N>  [<ai title>]`.
The token block is `read|cache_read|cache_write|out`, each right-aligned; the
pipes skip the column gap so they line up across the tree. The session status
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
    STATUS_ALIASES, SUBAGENT_RUNNING, SUBAGENT_SILENT, TOKEN_SEPARATOR,
)
from .models import HandRun, Session, Subagent, Usage
from .pricing import hand_usage
from .table import GROUP_TREE, Cell, Line
from .textwidth import truncate_display
from .timeutil import duration_text, ended_text, token_text, usd_text

UNKNOWN = "-"


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


def _context_cell(tokens: Optional[int]) -> Cell:
    context = token_text(tokens)
    return Cell(f"ctx {context}" if context else "")


def usage_cells(usage: Optional[Usage]) -> List[Cell]:
    """The `read|cache_read|cache_write|out` block plus the right-aligned USD cell."""
    values = ([None, None, None, None] if usage is None else
              [usage.read, usage.cache_read, usage.cache_write, usage.out])
    cells: List[Cell] = []
    for index, value in enumerate(values):
        if index:
            cells.append(Cell(TOKEN_SEPARATOR, glue=True))
        text = token_text(value) if value is not None else None
        cells.append(Cell(text or UNKNOWN, align_right=True, glue=index > 0))
    amount = usage.usd if usage is not None else None
    cells.append(Cell(usd_text(amount) or UNKNOWN, align_right=True))
    return cells


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
        _context_cell(session.context_tokens),
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
             _context_cell(session.context_tokens),
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
                size: str, duration: Optional[str], end: Optional[str],
                usage: Optional[Usage]) -> Line:
    cells = [Cell(child_kind(kind)), Cell(duration, align_right=True), Cell(end),
             *usage_cells(usage),
             Cell(size), Cell(truncate_display(description or "", DESCRIPTION_MAX_LEN)),
             Cell(status, key)]
    return Line("", cells, GROUP_TREE, Cell(mark, key))


def subagent_line(agent: Subagent, now: float) -> Line:
    context = token_text(agent.context_tokens)
    if agent.state == SUBAGENT_RUNNING:
        mark, key, status = CHILD_RUNNING_MARK, "running", ""
    elif agent.state == SUBAGENT_SILENT:
        mark, key, status = CHILD_RUNNING_MARK, "lost", SUBAGENT_SILENT
    else:
        mark, key, status = CHILD_OK_MARK, "finished", ""
    return _child_line(mark, key, agent.agent_type, agent.description, status,
                       f"ctx {context}" if context else "",
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
    output = token_text(run.tokens.get("output")) or "0"
    return _child_line(mark, key, run.backend, run.label or UNKNOWN, status,
                       f"out {output}", duration, ended_text(run.end_moment, now),
                       hand_usage(run.tokens, run.backend))
