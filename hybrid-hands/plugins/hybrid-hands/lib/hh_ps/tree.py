"""Assemble the hh-ps snapshot from every source and attach runs to sessions."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from .claude_source import claude_config_dir, load_sessions, short_session_id
from .constants import PARENT_SESSION_ENV
from .models import HandRun, Snapshot
from .registry_source import (
    SessionMeta, load_hand_runs, load_ps_config, load_session_meta, side_state_caps,
    state_root,
)


def project_root(cwd: Path) -> Path:
    try:
        done = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=True)
        return Path(done.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return cwd.resolve()


def _cap_for(session, meta: Dict[str, SessionMeta],
             side: Dict[str, dict]) -> Optional[int]:
    # `exempt` in a launcher .meta waives the daily budget only; the token cap still applies.
    found = meta.get(session.session_id)
    if found is not None and found.cap_tokens:
        return int(found.cap_tokens)
    state = side.get(session.session_id) or {}
    raw = state.get("max_tokens")
    try:
        cap = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        cap = None
    return cap if cap and cap > 0 else None


def _run_sort_key(run: HandRun):
    return (not run.running, -(run.started_at or 0.0), run.run_id)


def build_snapshot(cwd: Path, since_seconds: int, all_projects: bool,
                   now: Optional[float] = None,
                   main_session_id: Optional[str] = None) -> Snapshot:
    cwd = Path(cwd)
    moment = time.time() if now is None else float(now)
    cutoff = moment - since_seconds
    root = project_root(cwd)
    config = load_ps_config(root)
    main_session_id = main_session_id or os.environ.get(PARENT_SESSION_ENV) or None
    sessions = load_sessions(claude_config_dir(), cutoff, root, all_projects,
                             main_session_id, moment)
    meta = load_session_meta(config)
    side = side_state_caps(config)
    for session in sessions:
        found = meta.get(session.session_id)
        state = side.get(session.session_id) or {}
        if session.name == short_session_id(session.session_id) and state.get("name"):
            session.name = str(state["name"])
        if session.started_at is None and found is not None:
            session.started_at = found.started_at
        if session.started_at is None:
            try:
                session.started_at = (float(state["started"])
                                      if state.get("started") is not None else None)
            except (TypeError, ValueError):
                session.started_at = None
        session.token_cap = _cap_for(session, meta, side)
        if session.token_cap and session.context_tokens is not None:
            session.token_ratio = round(session.context_tokens / session.token_cap, 4)
    by_id = {session.session_id: session for session in sessions}
    orphans: List[HandRun] = []
    for run in load_hand_runs(state_root(), cutoff):
        parent = by_id.get(run.parent_session) if run.parent_session else None
        if parent is not None:
            parent.hand_runs.append(run)
        else:
            orphans.append(run)
    for session in sessions:
        session.hand_runs.sort(key=_run_sort_key)
    orphans.sort(key=_run_sort_key)
    return Snapshot(sessions=sessions, orphan_runs=orphans, since_seconds=since_seconds,
                    cwd=str(cwd), all_projects=all_projects,
                    main_session_id=main_session_id, generated_at=moment)
