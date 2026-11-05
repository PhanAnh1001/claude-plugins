"""Assemble the hh-ps snapshot from every source and attach runs to sessions."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .claude_source import claude_config_dir, load_sessions, short_session_id
from .constants import (
    PARENT_SESSION_ENV, PROVIDER_CLAUDE, RUN_STATUS_RUNNING, SIDE_RUN_LABEL_PREFIX,
)
from .models import HandRun, Session, Snapshot
from .registry_source import (
    SessionMeta, load_hand_runs, load_ps_config, load_session_meta, side_state_caps,
    state_root,
)
from .timeutil import to_epoch

SideMap = Dict[str, Dict[str, Any]]


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


def _positive(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _used_tokens(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _reachable_ids(side: SideMap, seeds: Set[str]) -> Set[str]:
    reached = set(seeds)
    changed = True
    while changed:
        changed = False
        for uuid, state in side.items():
            if uuid in reached:
                continue
            parent = state.get("parent_session")
            if parent and parent in reached:
                reached.add(uuid)
                changed = True
    return reached


def _claude_sessions(root: Path, cutoff: float, all_projects: bool,
                     main_session_id: Optional[str], moment: float,
                     side: SideMap) -> List[Session]:
    include_ids = set(side) if side else None
    sessions = load_sessions(claude_config_dir(), cutoff, root,
                             all_projects, main_session_id, moment,
                             include_ids=include_ids)
    seeds = {session.session_id for session in sessions if not session.pulled_in}
    reached = _reachable_ids(side, seeds)
    return [session for session in sessions
            if not session.pulled_in or session.session_id in reached]


def _apply_side_fields(session: Session, state: Dict[str, Any]) -> None:
    if not state:
        return
    session.parent_session = state.get("parent_session") or None
    session.side_name = state.get("name") or None
    session.provider = state.get("provider") or PROVIDER_CLAUDE


def _synthetic_session(uuid: str, state: Dict[str, Any]) -> Session:
    started = to_epoch(state.get("started"))
    status = str(state.get("status") or "")
    cap = _positive(state.get("max_tokens"))
    used = _used_tokens(state.get("tokens_used"))
    session = Session(
        session_id=uuid,
        name=state.get("name") or uuid,
        status=status,
        cwd=state.get("dir") or "",
        context_tokens=used,
        started_at=started,
        last_activity=started,
        is_main=False,
        live=status == RUN_STATUS_RUNNING,
        parent_session=state.get("parent_session") or None,
        side_name=state.get("name") or None,
        provider=state.get("provider") or PROVIDER_CLAUDE,
        token_cap=cap,
    )
    if cap:
        session.token_ratio = round(used / cap, 4)
    return session


def _add_external_sessions(sessions: List[Session], side: SideMap,
                           cutoff: float) -> None:
    visible = {session.session_id for session in sessions}
    added = True
    while added:
        added = False
        for uuid, state in side.items():
            if uuid in visible or state.get("provider") == PROVIDER_CLAUDE:
                continue
            parent = state.get("parent_session")
            if not parent or parent not in visible:
                continue
            started = to_epoch(state.get("started"))
            live = state.get("status") == RUN_STATUS_RUNNING
            if not live and started is not None and started < cutoff:
                continue
            sessions.append(_synthetic_session(uuid, state))
            visible.add(uuid)
            added = True


def _enrich(session: Session, meta: Dict[str, SessionMeta], side: SideMap) -> None:
    found = meta.get(session.session_id)
    state = side.get(session.session_id) or {}
    _apply_side_fields(session, state)
    if session.name == short_session_id(session.session_id) and state.get("name"):
        session.name = str(state["name"])
    if session.started_at is None and found is not None:
        session.started_at = found.started_at
    if session.started_at is None:
        session.started_at = to_epoch(state.get("started"))
    session.token_cap = _cap_for(session, meta, side)
    if session.token_cap and session.context_tokens is not None:
        session.token_ratio = round(session.context_tokens / session.token_cap, 4)


def _run_sort_key(run: HandRun):
    return (not run.running, -(run.started_at or 0.0), run.run_id)


def _side_run_targets(sessions: List[Session],
                      side: SideMap) -> Dict[str, Tuple[Session, Optional[float]]]:
    targets: Dict[str, Tuple[Session, Optional[float]]] = {}
    for session in sessions:
        if not session.side_name:
            continue
        state = side.get(session.session_id) or {}
        targets[SIDE_RUN_LABEL_PREFIX + session.side_name] = (
            session, to_epoch(state.get("started")))
    return targets


def _label_target(run: HandRun,
                  targets: Dict[str, Tuple[Session, Optional[float]]]) -> Optional[Session]:
    found = targets.get(run.label)
    if found is None:
        return None
    session, started = found
    if run.started_at is None or started is None or run.started_at < started:
        return None
    return session


def build_snapshot(cwd: Path, since_seconds: int, all_projects: bool,
                   now: Optional[float] = None,
                   main_session_id: Optional[str] = None) -> Snapshot:
    cwd = Path(cwd)
    moment = time.time() if now is None else float(now)
    cutoff = moment - since_seconds
    root = project_root(cwd)
    config = load_ps_config(root)
    main_session_id = main_session_id or os.environ.get(PARENT_SESSION_ENV) or None
    meta = load_session_meta(config)
    side = side_state_caps(config)
    sessions = _claude_sessions(root, cutoff, all_projects, main_session_id,
                                moment, side)
    _add_external_sessions(sessions, side, cutoff)
    for session in sessions:
        _enrich(session, meta, side)
    by_id = {session.session_id: session for session in sessions}
    targets = _side_run_targets(sessions, side)
    orphans: List[HandRun] = []
    for run in load_hand_runs(state_root(), cutoff):
        target = _label_target(run, targets)
        if target is None and run.parent_session and \
                not run.label.startswith(SIDE_RUN_LABEL_PREFIX):
            target = by_id.get(run.parent_session)
        if target is not None:
            target.hand_runs.append(run)
        else:
            orphans.append(run)
    for session in sessions:
        session.hand_runs.sort(key=_run_sort_key)
    orphans.sort(key=_run_sort_key)
    return Snapshot(sessions=sessions, orphan_runs=orphans, since_seconds=since_seconds,
                    cwd=str(cwd), all_projects=all_projects,
                    main_session_id=main_session_id, generated_at=moment)
