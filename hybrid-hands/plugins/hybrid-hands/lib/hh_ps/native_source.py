"""Local Codex child metadata only; never decode response/chat records."""
from __future__ import annotations

from dataclasses import replace

import json
import math
import re
from pathlib import Path

from .codex import _HEADER_META, _contained, _sessions_root, _priced_tokens, codex_home, rollout_week
from .models import Session, Subagent, Usage
from .registry_source import _exit_code
from .timeutil import to_epoch

_HEADER = re.compile(r'^\s*\{\s*' + _HEADER_META +
    r'"type"\s*:\s*"(session_meta|turn_context|event_msg)"\s*,\s*' +
    _HEADER_META + r'"payload"\s*:\s*\{')
_EVENT = re.compile(r'"payload"\s*:\s*\{\s*"type"\s*:\s*"(task_started|task_complete|task_failed|task_errored|task_cancelled|turn_aborted|failed|errored|cancelled|token_count)"\s*[,}]')


def _records(path, token_only=False, strict=False):
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = _HEADER.match(line)
                if not match or (match[1] == "event_msg" and not _EVENT.search(line)):
                    continue
                if token_only and match[1] == "event_msg" and not re.search(
                        r'"payload"\s*:\s*\{\s*"type"\s*:\s*"token_count"\s*[,}]', line):
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    if strict:
                        raise
                    continue
                payload = row.get("payload")
                if isinstance(payload, dict):
                    keys = {"id", "parent_thread_id", "source", "cwd", "timestamp", "model", "effort", "reasoning_effort", "description", "title", "agent_path", "agent_nickname"} if row["type"] != "event_msg" else {"type", "started_at", "completed_at", "ended_at", "duration_ms", "exit_code", "exit", "status", "info", "rate_limits"}
                    yield row["type"], {k: v for k, v in payload.items() if k in keys}, to_epoch(row.get("timestamp"))
    except OSError:
        if strict:
            raise
        return


def _metadata_name(metadata, spawn=None):
    """Use explicit metadata only, never infer a label from prompt/chat text."""
    spawn = spawn or {}
    for key in ("description", "title", "agent_path", "agent_nickname"):
        for source in (metadata, spawn):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _read(path, now):
    sid = parent = model = effort = name = ""
    status = "unknown"
    start = end = activity = duration = exit_code = tokens = None
    identity_seen = inherited = forked = False
    for kind, p, stamp in _records(path):
        if kind == "session_meta":
            # Fork rollouts begin with their own identity, then replay ancestor
            # metadata/history. Those later headers must never reparent the file.
            if identity_seen:
                inherited = str(p.get("id") or "") != sid
                forked = forked or inherited
                continue
            identity_seen = True
            sid = str(p.get("id") or "")
            source = p.get("source")
            sub = source.get("subagent") if isinstance(source, dict) else None
            spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
            spawn = spawn if isinstance(spawn, dict) else {}
            parent = str(p.get("parent_thread_id") or spawn.get("parent_thread_id") or "")
            name = _metadata_name(p, spawn)
            start = to_epoch(p.get("timestamp")) or stamp
            model = str(p.get("model") or model)
            effort = str(p.get("effort") or effort)
            continue
        # An ancestor's completion, model or token total is not child evidence.
        # Resume only at an observed child-time record; missing bounds stay
        # unknown rather than borrowing the ancestor's activity or usage.
        if inherited:
            if start is None or stamp is None or stamp < start:
                continue
            inherited = False
        if start is not None and stamp is not None and stamp < start:
            continue
        if kind == "turn_context":
            model = str(p.get("model") or model)
            effort = str(p.get("effort") or p.get("reasoning_effort") or effort)
        else:
            event = p.get("type")
            if event == "token_count":
                info = p.get("info")
                raw = info.get("total_token_usage") if isinstance(info, dict) else None
                tokens = (_priced_tokens(raw) if isinstance(raw, dict) and all(
                    isinstance(raw.get(k), int) and not isinstance(raw.get(k), bool) and raw[k] >= 0
                    for k in ("input_tokens", "output_tokens")) else None)
            else:
                activity = stamp
                exit_code = _exit_code(p.get("exit_code", p.get("exit")))
                if event == "task_started":
                    status, end, duration = "running", None, None
                    start = start if start is not None else (to_epoch(p.get("started_at")) or stamp)
                else:
                    status = ("completed" if event == "task_complete" else
                              "cancelled" if event == "turn_aborted" else str(event).removeprefix("task_"))
                    if str(p.get("status") or "") in ("failed", "errored", "cancelled", "error"):
                        status = str(p["status"])
                    end = to_epoch(p.get("completed_at") or p.get("ended_at")) or stamp
                    ms = p.get("duration_ms")
                    if isinstance(ms, (int, float)) and not isinstance(ms, bool) and math.isfinite(ms) and ms >= 0:
                        duration = ms / 1000
    if exit_code not in (None, 0):
        status = "error"
    if start is not None and (end is not None or status == "running"):
        duration = max(0, (end if end is not None else now) - start)
    usage = None
    if tokens is not None:
        usage = Usage(read=max(0, tokens["input"] - tokens["cached_input"]),
                      cache_read=tokens["cached_input"], out=tokens["output"])
    # The whole-file quota reader cannot separate inherited fork samples.
    measured = None if forked else rollout_week(path, now)
    if measured is not None:
        usage = usage or Usage(usd=None)
        usage = replace(usage, week_pct=measured, week_pct_source="codex_rate_limits_delta")
    agent = Subagent(sid, "native-codex", name, status not in ("running", "unknown"),
                     False, None, duration, activity, usage, start, model, effort,
                     "codex", status, exit_code, end)
    return sid, parent, agent


def discover_main_sessions(sessions: list[Session], pinned: dict[str, str],
                           project: Path, all_projects: bool, cutoff: float,
                           now: float, main_session_id: str | None, *, managed_runs=()) -> None:
    """Discover unregistered roots from local metadata before attaching children.

    A pinned thread already has a canonical side-session identity. Never create a
    second root for that rollout, or promote a native child to a main session.
    """
    from .claude_source import _in_project, short_session_id

    root = _sessions_root(codex_home(None))
    if root is None:
        return
    known = {session.session_id for session in sessions}
    for raw in pinned.values():
        path = _contained(root, Path(raw)) if Path(raw).is_absolute() else None
        if path is None:
            continue
        for kind, payload, _ in _records(path):
            if kind == "session_meta":
                known.add(str(payload.get("id") or ""))
                break
    try:
        candidates = sorted(root.rglob("rollout-*.jsonl"))
    except OSError:
        return
    for candidate in candidates:
        path = _contained(root, candidate)
        if path is None:
            continue
        metadata = next((payload for kind, payload, _ in _records(path)
                         if kind == "session_meta"), None)
        if metadata is None:
            continue
        from .paseo_source import managed_metadata
        if managed_metadata(metadata, managed_runs):
            continue
        sid = metadata.get("id")
        cwd = metadata.get("cwd")
        source = metadata.get("source")
        if not isinstance(sid, str) or not sid or sid in known:
            continue
        if metadata.get("parent_thread_id") or (
                isinstance(source, dict) and "subagent" in source):
            continue
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            continue
        if not all_projects and not _in_project(cwd, "", project):
            continue
        _, parent, agent = _read(path, now)
        if parent:
            continue
        # Use observed event/start timestamps, never filesystem mtime for recency.
        activity = agent.last_activity or agent.started_at
        if activity is None or activity < cutoff:
            continue
        session = Session(
            session_id=sid, name=agent.description or short_session_id(sid), status=agent.status,
            cwd=cwd, context_tokens=None, started_at=agent.started_at,
            last_activity=agent.last_activity, is_main=sid == main_session_id,
            live=agent.running, provider="codex", model=agent.model,
            effort=agent.effort, finished_at=agent.finished_at,
        )
        sessions.append(session)
        known.add(sid)
        # Reuse the existing rollout usage path, with no synthetic ledger/state.
        pinned[sid] = str(path)


def attach_native(sessions, pinned, now, *, managed_runs=()):
    home = codex_home(None)
    root = _sessions_root(home)
    if root is None:
        return
    aliases = {s.session_id: s for s in sessions}
    for session in sessions:
        raw = pinned.get(session.session_id)
        path = _contained(root, Path(raw)) if raw and Path(raw).is_absolute() else None
        if path is not None:
            for kind, payload, _ in _records(path):
                if kind == "session_meta" and payload.get("id"):
                    aliases[str(payload["id"])] = session
                    break
    seen = set()
    try:
        paths = sorted(root.rglob("rollout-*.jsonl"))
    except OSError:
        return
    for candidate in paths:
        path = _contained(root, candidate)
        if path is None:
            continue
        native_parent = ""
        managed = False
        for kind, payload, _ in _records(path):
            if kind == "session_meta":
                from .paseo_source import managed_metadata
                managed = managed_metadata(payload, managed_runs)
                source = payload.get("source") or {}
                sub = source.get("subagent") if isinstance(source, dict) else None
                spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
                native_parent = payload.get("parent_thread_id") or (spawn.get("parent_thread_id") if isinstance(spawn, dict) else "")
                break
        if managed or native_parent not in aliases:
            continue
        sid, parent, agent = _read(path, now)
        target = aliases.get(parent)
        if sid and target is not None and sid not in aliases and sid not in seen:
            target.subagents.append(agent)
            seen.add(sid)
