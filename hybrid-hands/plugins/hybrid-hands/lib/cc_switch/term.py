"""`cc-switch term`: hand one Paseo agent's session to the Claude Code TUI."""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import List, Optional

from .agents import (
    by_session, describe_agent, load_agents, match_agent_ref, project_agents,
)
from .constants import (
    EXIT_CONFLICT, EXIT_NOT_FOUND, EXIT_PASEO, EXIT_USAGE, STATUS_RUNNING,
)
from .errors import CcSwitchError
from .handoff import record as record_handoff
from .models import Agent
from .paseo_cli import PaseoError, statuses as paseo_statuses
from .paseo_cli import wait as paseo_wait
from .paths import resolve_project, short_id
from .sessions import tui_pids


def _agent_session(agent: Agent, fallback: Optional[str]) -> str:
    session_id = fallback or agent.session_id()
    if not session_id:
        raise CcSwitchError(
            f"Agent {short_id(agent.id)} không có sessionId để resume.",
            EXIT_NOT_FOUND)
    return session_id


def _single(matches: List[Agent], source: str) -> Agent:
    if len(matches) == 1:
        return matches[0]
    lines = [f"Nhiều agent khớp {source}; chọn một bằng --agent <id|tiền tố>:"]
    lines.extend(describe_agent(agent, index)
                 for index, agent in enumerate(matches, 1))
    raise CcSwitchError("\n".join(lines), EXIT_USAGE, to_stdout=True)


def select_agent(agents: List[Agent], root: Path, agent_ref: Optional[str],
                 session_id: Optional[str]) -> Agent:
    if agent_ref and session_id:
        raise CcSwitchError("Chỉ dùng một trong --agent hoặc --session.")
    if session_id:
        matches = by_session(agents, session_id)
        if not matches:
            raise CcSwitchError(
                f"Không có agent Paseo cho session {session_id}.\n"
                "Gợi ý: mở phiên đó trong Paseo trước, hoặc dùng `cc-switch status`.",
                EXIT_NOT_FOUND)
        return _single(matches, f"session {session_id}")
    if agent_ref:
        matches = match_agent_ref(agents, agent_ref)
        if not matches:
            raise CcSwitchError(
                f"Không tìm thấy agent khớp `{agent_ref}`.\n"
                "Gợi ý: xem id bằng `cc-switch status`.",
                EXIT_NOT_FOUND)
        return _single(matches, f"`{agent_ref}`")
    matches = project_agents(agents, root)
    if not matches:
        raise CcSwitchError(
            f"Không có agent Paseo provider claude cho project {root}.\n"
            "Gợi ý: tạo agent trong Paseo, hoặc chạy "
            "`cc-switch paseo --session <sessionId>` sau khi mở phiên trong terminal; "
            "xem `cc-switch status`.",
            EXIT_NOT_FOUND)
    if len(matches) > 1:
        lines = ["Nhiều agent Claude trong project; chọn một bằng --agent <id|tiền tố>:"]
        lines.extend(describe_agent(agent, index)
                     for index, agent in enumerate(matches, 1))
        raise CcSwitchError("\n".join(lines), EXIT_USAGE, to_stdout=True)
    return matches[0]


def _claude_argv(agent: Agent, session_id: str, extra: List[str]) -> List[str]:
    argv = ["claude", "--resume", session_id]
    if agent.runtime_model:
        argv.extend(["--model", agent.runtime_model])
    argv.extend(extra)
    return argv


def _current_status(agent: Agent) -> str:
    try:
        live = paseo_statuses()
    except PaseoError:
        live = {}
    return (live.get(agent.id) or agent.last_status).lower()


def _conflict(session_id: str, pids: List[int]) -> CcSwitchError:
    pid_text = ", ".join(str(pid) for pid in pids)
    return CcSwitchError(
        f"Phiên {short_id(session_id)} vẫn đang mở trong terminal (pid {pid_text}).\n"
        "Thoát Claude Code (/exit) rồi chạy lại lệnh này.",
        EXIT_CONFLICT)


def run_term(opts) -> int:
    root = resolve_project()
    agent = select_agent(load_agents(), root, opts.agent, opts.session)
    session_id = _agent_session(agent, opts.session)
    pids = tui_pids(session_id)
    if pids:
        raise _conflict(session_id, pids)

    argv = _claude_argv(agent, session_id, opts.extra)
    if opts.dry_run:
        print(shlex.join(argv))
        return 0

    if _current_status(agent) == STATUS_RUNNING:
        print("đang chờ agent rảnh…", flush=True)
        paseo_wait(agent.id)
        pids = tui_pids(session_id)
        if pids:
            raise _conflict(session_id, pids)

    try:
        os.chdir(agent.cwd)
    except OSError as exc:
        raise CcSwitchError(
            f"Không vào được thư mục agent {agent.cwd}: {exc}", EXIT_PASEO) from exc
    record_handoff(root, session_id, agent.id)
    print(f"Đang dùng ở terminal: đừng gửi tin cho agent {short_id(agent.id)} "
          "từ Paseo cho tới khi chạy `cc-switch paseo`.", flush=True)
    try:
        os.execvp("claude", argv)
    except OSError as exc:
        raise CcSwitchError(f"Không chạy được `claude`: {exc}", EXIT_PASEO) from exc
    return EXIT_PASEO
