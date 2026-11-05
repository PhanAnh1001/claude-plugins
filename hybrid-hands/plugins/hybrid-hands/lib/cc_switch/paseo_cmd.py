"""`cc-switch paseo`: reload or import one session so Paseo owns it again."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .agents import by_session, load_agents, preferred_agent
from .constants import (
    EXIT_CONFLICT, EXIT_NOT_FOUND, HANDOFF_TIME_FORMAT, UNKNOWN_TIME,
    UNKNOWN_TITLE,
)
from .errors import CcSwitchError
from .handoff import forget as forget_handoff, lookup as lookup_handoff
from .models import Agent, Transcript
from .paseo_cli import command_line, import_session, reload_agent
from .paths import resolve_project, short_id
from .sessions import (
    find_transcript, live_session_cwd, newest_project_transcript,
    read_custom_title, tui_pids,
)


@dataclass(frozen=True)
class _Picked:
    session_id: str
    cwd: str
    from_handoff: bool
    transcript: Optional[Transcript]


def _normalize(cwd: str) -> str:
    try:
        return str(Path(cwd).resolve())
    except (OSError, RuntimeError):
        return cwd


def _cwd_for(transcript: Optional[Transcript], session_id: str,
             fallback: str = "") -> str:
    cwd = transcript.cwd if transcript is not None else ""
    cwd = cwd or live_session_cwd(session_id) or fallback
    return _normalize(cwd) if cwd else ""


def _pick_session(opts, root: Path) -> _Picked:
    """Return the session to hand back; prefer the `term` handoff ledger."""
    if opts.session:
        transcript = find_transcript(opts.session)
        return _Picked(opts.session, _cwd_for(transcript, opts.session),
                       False, transcript)

    entry = lookup_handoff(root)
    if entry is not None:
        transcript = find_transcript(entry.session_id)
        if transcript is not None:
            return _Picked(entry.session_id,
                           _cwd_for(transcript, entry.session_id), True,
                           transcript)

    transcript = newest_project_transcript(root)
    if transcript is None:
        raise CcSwitchError(
            f"Không có transcript nào có dòng user trong project {root}.\n"
            "Gợi ý: mở Claude Code trong project này trước, hoặc dùng --session.",
            EXIT_NOT_FOUND)
    return _Picked(transcript.session_id,
                   _cwd_for(transcript, transcript.session_id, str(root)),
                   False, transcript)


def _epoch(value: str) -> Optional[float]:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _session_name(transcript: Optional[Transcript],
                  agent: Optional[Agent]) -> str:
    if transcript is not None:
        title = transcript.title or read_custom_title(transcript.path)
        if title:
            return title
    if agent is not None and agent.title:
        return agent.title
    return UNKNOWN_TITLE


def _session_time(transcript: Optional[Transcript],
                  agent: Optional[Agent]) -> str:
    if transcript is not None:
        moment: Optional[float] = transcript.mtime
    else:
        moment = _epoch(agent.last_activity) if agent is not None else None
    if moment is None:
        return UNKNOWN_TIME
    return time.strftime(HANDOFF_TIME_FORMAT, time.localtime(moment))


def _session_line(session_id: str, transcript: Optional[Transcript],
                  agent: Optional[Agent]) -> str:
    return (f"session {short_id(session_id)} — "
            f"{_session_name(transcript, agent)} — "
            f"sửa lúc {_session_time(transcript, agent)}")


def _conflict(session_id: str, pids) -> CcSwitchError:
    pid_text = ", ".join(str(pid) for pid in pids)
    return CcSwitchError(
        f"Phiên {short_id(session_id)} vẫn đang mở trong terminal (pid {pid_text}).\n"
        "Thoát Claude Code (/exit) rồi chạy lại lệnh này.",
        EXIT_CONFLICT)


def _forget(root: Path, explicit_session: Optional[str],
            session_id: str) -> None:
    if explicit_session:
        forget_handoff(root, session_id)
    else:
        forget_handoff(root)


def run_paseo(opts) -> int:
    root = resolve_project()
    picked = _pick_session(opts, root)
    session_id = picked.session_id
    pids = tui_pids(session_id)
    if pids:
        raise _conflict(session_id, pids)

    agent: Optional[Agent] = None
    matches = by_session(load_agents(), session_id)
    if matches:
        agent = preferred_agent(matches)
        args = ["agent", "reload", agent.id]
    else:
        if not picked.cwd:
            raise CcSwitchError(
                f"Không tìm thấy transcript hay phiên sống cho session {session_id}.\n"
                "Gợi ý: kiểm tra `cc-switch status` hoặc mở phiên đó một lần "
                "trong terminal.",
                EXIT_NOT_FOUND)
        args = ["import", session_id, "--provider", "claude",
                "--cwd", picked.cwd, "--json"]

    print(_session_line(session_id, picked.transcript, agent), flush=True)
    if picked.from_handoff:
        print("theo sổ bàn giao của `cc-switch term`", flush=True)
    if opts.dry_run:
        print(command_line(args))
        return 0

    if agent is not None:
        reload_agent(agent.id)
        print(f"agent {agent.id}")
        print(f"đã nạp lại agent Paseo (session {short_id(session_id)})")
    else:
        agent_id = import_session(session_id, picked.cwd)
        print(f"agent {agent_id}")
        print(f"đã import phiên {short_id(session_id)} vào Paseo")
    _forget(root, opts.session, session_id)
    print("mở Paseo trên điện thoại để tiếp tục")
    return 0
