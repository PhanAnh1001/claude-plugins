"""Assemble the hh-ps snapshot from every source and attach runs to sessions."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from hand_ext.constants import GO_USAGE_BACKENDS

from .claude_source import claude_config_dir, load_sessions, short_session_id
from .codex import CodexData, load_codex, pinned_rollouts
from .constants import (
    PARENT_SESSION_ENV, PROVIDER_CLAUDE, PROVIDER_CODEX, RUN_STATUS_RUNNING,
    SIDE_RUN_LABEL_PREFIX, SIDE_RUN_LABEL_SANITIZED_PREFIX,
)
from .limits import collect_limits, load_hand_ext_config
from .models import HandRun, Session, Snapshot
from .registry_source import SessionMeta, load_hand_runs, load_ps_config, state_root
from .repos import RepoState, SideMap, project_root
from .timeutil import to_epoch
from .week import (ClaudeWeek, GoWeek, apply_claude_week, read_claude_week,
                   read_go_week)


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
                     side: SideMap, since: Optional[float]) -> List[Session]:
    include_ids = set(side) if side else None
    sessions = load_sessions(claude_config_dir(), cutoff, root,
                             all_projects, main_session_id, moment,
                             include_ids=include_ids, since=since)
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
    session.model = state.get("model") or session.model
    session.effort = state.get("effort") or session.effort
    session.finished_at = to_epoch(state.get("ended_at")) or session.finished_at


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
        last_activity=None,
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
                           cutoff: float, root: Path, all_projects: bool) -> None:
    visible = {session.session_id for session in sessions}
    added = True
    while added:
        added = False
        for uuid, state in side.items():
            if uuid in visible:
                continue
            parent = state.get("parent_session")
            if not parent or parent not in visible:
                from .claude_source import _in_project
                if not all_projects and not _in_project(str(state.get("dir") or ""), "", root):
                    continue
            started = to_epoch(state.get("started"))
            if started is not None and started < cutoff:
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


def _session_dirs(sessions: List[Session]) -> List[str]:
    return [session.cwd for session in sessions if session.cwd]


def _run_sort_key(run: HandRun):
    return (not run.running, -(run.started_at or 0.0), run.run_id)


def _side_run_targets(sessions: List[Session],
                      side: SideMap) -> Dict[str, Tuple[Session, Optional[float]]]:
    targets: Dict[str, Tuple[Session, Optional[float]]] = {}
    for session in sessions:
        if not session.side_name:
            continue
        state = side.get(session.session_id) or {}
        found = (session, to_epoch(state.get("started")))
        for prefix in (SIDE_RUN_LABEL_PREFIX, SIDE_RUN_LABEL_SANITIZED_PREFIX):
            targets[prefix + session.side_name] = found
    return targets


def _label_target(run: HandRun,
                  targets: Dict[str, Tuple[Session, Optional[float]]]) -> Optional[Session]:
    found = targets.get(run.label)
    if found is None:
        return None
    session, started = found
    # The registry stores `started` with second precision; state.started is fractional.
    if run.started_at is None or started is None or run.started_at < int(started):
        return None
    return session


def _run_in_week(run: HandRun, week: Optional[GoWeek]) -> bool:
    if week is None:
        return False
    return run.ended_at is None or run.ended_at >= week.window_start


def _apply_run_week(run: HandRun, week: Optional[GoWeek]) -> None:
    if run.backend not in GO_USAGE_BACKENDS:
        run.week_limit_usd = None
        run.week_pct_estimated = False
        return
    run.week_limit_usd = (week.limit_usd
                          if week is not None and _run_in_week(run, week)
                          else None)
    run.week_pct_estimated = bool(week and week.total_estimated)


def _apply_weeks(sessions: List[Session], claude_week: Optional[ClaudeWeek],
                 go_week: Optional[GoWeek]) -> None:
    for session in sessions:
        # Claude's weekly share only belongs to Claude rows; Codex gets GPT samples
        # and Go hand runs get their own weekly formula.
        if session.provider == PROVIDER_CLAUDE:
            session.usage = apply_claude_week(session.usage, claude_week)
        for agent in session.subagents:
            agent.usage = apply_claude_week(agent.usage, claude_week)
        for run in session.hand_runs:
            _apply_run_week(run, go_week)


def _rollout_metadata(session: Session, path: Path) -> None:
    """Keep only session/turn metadata from a pinned rollout, never chat payloads."""
    import json
    import re
    header_meta = (r'(?:"timestamp"\s*:\s*"[^"]*"\s*,\s*)?'
                   r'(?:"ordinal"\s*:\s*-?\d+\s*,\s*)?')
    header = re.compile(r'^\s*\{\s*' + header_meta +
                        r'"type"\s*:\s*"(?:session_meta|turn_context)"\s*[,}]')
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not header.match(line):
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                metadata = payload.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else {}
                reasoning = payload.get("reasoning")
                reasoning = reasoning if isinstance(reasoning, dict) else {}
                session.model = str(payload.get("model") or metadata.get("model") or session.model)
                session.effort = str(payload.get("effort") or
                                     payload.get("reasoning_effort") or reasoning.get("effort") or
                                     metadata.get("effort") or
                                     metadata.get("reasoning_effort") or session.effort)
                if item.get("type") == "session_meta":
                    session.started_at = to_epoch(payload.get("timestamp")) or session.started_at
    except OSError:
        return


def _apply_codex(sessions: List[Session], orphans: List[HandRun],
                 codex: CodexData, rollouts: Dict[str, str], now: float) -> None:
    """Attach each Codex row's own usage from its ledger line or pinned rollout."""
    for session in sessions:
        if session.provider != PROVIDER_CODEX:
            continue
        path = codex.contained_rollout(rollouts.get(session.session_id))
        if path is not None:
            _rollout_metadata(session, path)
        usage = codex.rollout_usage(rollouts.get(session.session_id), now)
        if usage is not None:
            session.usage = usage
    runs = [run for session in sessions for run in session.hand_runs] + orphans
    for run in runs:
        if run.backend != PROVIDER_CODEX:
            continue
        if run.execution_key:
            # A run-id-only historical ledger must not fill an unknown parser
            # result or lend another epoch's quota samples to this execution.
            entry = codex.ledger.get(run.run_id) or {}
            if not run.tokens or entry.get("execution_key") != run.execution_key:
                continue
        usage = codex.hand_usage(run.run_id, run.tokens, now)
        if usage is not None:
            run.usage = usage


def build_snapshot(cwd: Path, since_seconds: int, all_projects: bool,
                   now: Optional[float] = None,
                   main_session_id: Optional[str] = None) -> Snapshot:
    cwd = Path(cwd)
    moment = time.time() if now is None else float(now)
    cutoff = moment - since_seconds
    # The hand-ext config owns the repo root and the Go limit; read it once and reuse
    # its root instead of running git --show-toplevel a second time.
    cfg = load_hand_ext_config(cwd)
    root = cfg.root if cfg is not None else project_root(cwd)
    home = claude_config_dir()
    claude_week = read_claude_week(home, moment)
    go_week = read_go_week(cfg.machine_state_dir if cfg is not None else state_root(),
                           home, moment)
    since = claude_week.window_start if claude_week is not None else None
    main_session_id = main_session_id or os.environ.get(PARENT_SESSION_ENV) or None
    repos = RepoState()
    repos.add_root(root, load_ps_config(root))
    sessions = _claude_sessions(root, cutoff, all_projects, main_session_id,
                                moment, repos.side, since)
    if repos.add_cwds(_session_dirs(sessions)):
        # Side state from another repo may pull in ended sessions; load once more.
        sessions = _claude_sessions(root, cutoff, all_projects, main_session_id,
                                    moment, repos.side, since)
    meta, side = repos.meta, repos.side
    _add_external_sessions(sessions, side, cutoff, root, all_projects)
    for session in sessions:
        _enrich(session, meta, side)
    pinned = pinned_rollouts(repos.roots)
    runs = load_hand_runs(state_root(), cutoff, repos.roots,
                         known_configs={root: cfg}, config_files=repos.config_files())
    from .native_source import discover_main_sessions
    discover_main_sessions(sessions, pinned, root, all_projects, cutoff, moment,
                           main_session_id, managed_runs=runs)
    from .paseo_source import dedup_native
    dedup_native(sessions, runs)
    by_id = {session.session_id: session for session in sessions}
    targets = _side_run_targets(sessions, side)
    orphans: List[HandRun] = []
    for run in runs:
        target = by_id.get(run.parent_session) if run.execution_key else _label_target(run, targets)
        side_label = not run.execution_key and (run.label in targets or run.label.startswith(SIDE_RUN_LABEL_PREFIX))
        if target is None and run.parent_session and not side_label:
            target = by_id.get(run.parent_session)
        if target is not None:
            target.hand_runs.append(run)
        else:
            orphans.append(run)
    for session in sessions:
        session.hand_runs.sort(key=_run_sort_key)
    orphans.sort(key=_run_sort_key)
    _apply_weeks(sessions, claude_week, go_week)
    for run in orphans:
        _apply_run_week(run, go_week)
    codex = load_codex(cfg, moment)
    _apply_codex(sessions, orphans, codex, pinned, moment)
    from .native_source import attach_native
    attach_native(sessions, pinned, moment, managed_runs=runs)
    dedup_native(sessions, runs)
    snapshot = Snapshot(sessions=sessions, orphan_runs=orphans, since_seconds=since_seconds,
                    cwd=str(cwd), all_projects=all_projects,
                    main_session_id=main_session_id, generated_at=moment,
                    limits=collect_limits(root, moment, cfg=cfg,
                                          claude_week=claude_week, go_week=go_week,
                                          codex_windows=codex.account))

    from .machine_usage import machine_usage
    snapshot.machine_usage = machine_usage(home, claude_week, codex, cfg, moment)
    from .usage_enrichment import enrich_snapshot
    enrich_snapshot(snapshot, cfg, moment)
    from .claude_calibration import enrich
    enrich(snapshot, time.time() if now is None else moment)
    return snapshot
