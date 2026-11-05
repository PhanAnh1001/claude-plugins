"""`cc-switch status`: who currently holds each Claude session."""
from __future__ import annotations

import sys
from typing import List

from .agents import load_agents
from .constants import (
    HOLDER_NONE, HOLDER_PASEO, HOLDER_TERMINAL, PASEO_ACTIVE_STATUSES,
    PASEO_STATUS_WIDTH, PROVIDER_CLAUDE, SESSION_ENTRYPOINT_TUI,
    SHORT_ID_CHARS, STATUS_HEADER, TITLE_MAX_CHARS, TUI_WIDTH,
)
from .models import Agent, LiveSession
from .paseo_cli import PaseoError, statuses as paseo_statuses
from .paths import display, resolve_project, same_path, short_id
from .sessions import live_sessions


def _holder(agent: Agent, paseo_status: str, pids: List[int]) -> str:
    if pids:
        return HOLDER_TERMINAL
    if not agent.archived and paseo_status in PASEO_ACTIVE_STATUSES:
        return HOLDER_PASEO
    return HOLDER_NONE


def _pids(agent: Agent, live: List[LiveSession]) -> List[int]:
    session_id = agent.session_id()
    if not session_id:
        return []
    return sorted({item.pid for item in live
                   if item.session_id == session_id
                   and item.entrypoint == SESSION_ENTRYPOINT_TUI})


def _row(agent: Agent, paseo_status: str, live: List[LiveSession]) -> str:
    pids = _pids(agent, live)
    tui = ",".join(str(pid) for pid in pids) if pids else "-"
    title = display(agent.title or "(không tên)", TITLE_MAX_CHARS)
    return (f"{short_id(agent.id):<{SHORT_ID_CHARS}}  "
            f"{title:<{TITLE_MAX_CHARS}}  "
            f"{paseo_status:<{PASEO_STATUS_WIDTH}}  "
            f"{short_id(agent.session_id()):<{SHORT_ID_CHARS}}  "
            f"{tui:<{TUI_WIDTH}}  {_holder(agent, paseo_status, pids)}")


def run_status(opts) -> int:
    root = resolve_project()
    agents = [agent for agent in load_agents()
              if agent.provider == PROVIDER_CLAUDE
              and (opts.all or same_path(agent.cwd, root))]
    try:
        paseo_map = paseo_statuses()
    except PaseoError as exc:
        paseo_map = {}
        print(f"paseo ls lỗi: {exc.message}", file=sys.stderr)
    live = live_sessions()
    print(STATUS_HEADER)
    for agent in sorted(agents, key=lambda item: (item.title.lower(), item.id)):
        current = paseo_map.get(agent.id) or agent.last_status or "-"
        print(_row(agent, current, live))
    return 0
