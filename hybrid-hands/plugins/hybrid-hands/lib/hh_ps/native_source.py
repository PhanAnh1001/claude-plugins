"""Local Codex child metadata only; never decode response/chat records."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .codex import _HEADER_META, _contained, _sessions_root, _priced_tokens, codex_home
from .models import Subagent, Usage
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
                    keys = {"id", "parent_thread_id", "source", "timestamp", "model", "effort", "reasoning_effort"} if row["type"] != "event_msg" else {"type", "started_at", "completed_at", "ended_at", "duration_ms", "exit_code", "exit", "status", "info"}
                    yield row["type"], {k: v for k, v in payload.items() if k in keys}, to_epoch(row.get("timestamp"))
    except OSError:
        if strict:
            raise
        return


def _read(path, now):
    sid = parent = model = effort = name = ""
    status = "unknown"
    start = end = activity = duration = exit_code = tokens = None
    for kind, p, stamp in _records(path):
        if kind == "session_meta":
            sid = str(p.get("id") or "")
            source = p.get("source")
            sub = source.get("subagent") if isinstance(source, dict) else None
            spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
            spawn = spawn if isinstance(spawn, dict) else {}
            parent = str(p.get("parent_thread_id") or spawn.get("parent_thread_id") or "")
            name = str(spawn.get("agent_nickname") or spawn.get("agent_path") or "")
            start = to_epoch(p.get("timestamp")) or stamp
            model = str(p.get("model") or model)
            effort = str(p.get("effort") or effort)
        elif kind == "turn_context":
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
    agent = Subagent(sid, "native-codex", name, status not in ("running", "unknown"),
                     False, None, duration, activity, usage, start, model, effort,
                     "codex", status, exit_code, end)
    return sid, parent, agent


def attach_native(sessions, pinned, now):
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
        for kind, payload, _ in _records(path):
            if kind == "session_meta":
                source = payload.get("source") or {}
                sub = source.get("subagent") if isinstance(source, dict) else None
                spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
                native_parent = payload.get("parent_thread_id") or (spawn.get("parent_thread_id") if isinstance(spawn, dict) else "")
                break
        if native_parent not in aliases:
            continue
        sid, parent, agent = _read(path, now)
        target = aliases.get(parent)
        if sid and target is not None and sid not in aliases and sid not in seen:
            target.subagents.append(agent)
            seen.add(sid)
