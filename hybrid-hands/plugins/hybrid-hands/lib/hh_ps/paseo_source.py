"""Read-only projection of durable managed executions, never ACP/chat payloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hand_ext.execution_state import ExecutionRecord, _plain

from .models import HandRun
from .timeutil import to_epoch


def execution_id(key):
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def _json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def load_executions(roots, cutoff):
    """One row per exact key; outcome/parser totals replace, never sum, sinks."""
    records = {}
    for root in sorted(set(map(Path, roots))):
        for path in sorted(root.glob("*.json")):
            try:
                record = ExecutionRecord.from_dict(_json(path))
            except (ValueError, TypeError, KeyError):
                continue
            if record.invocation.origin not in ("managed", "native_intent"):
                continue
            key = execution_id(_plain(record.key))
            if key not in records or record.revision > records[key].revision:
                records[key] = record
    runs = []
    for key, record in records.items():
        invocation, attempt = record.invocation, record.attempt
        receipt, outcome = record.receipt or {}, record.outcome or {}
        report = record.artifacts.get("report") or {}
        run_id = attempt.run_id or key
        # Only machine-readable completion metadata; never read report prose.
        metadata = {}
        completion = receipt.get("completion") or {}
        candidates = [report.get("metadata"), report.get("registry")]
        if receipt.get("worker_run_dir"):
            candidates.append(Path(receipt["worker_run_dir"]) / "meta.json")
        if completion.get("registry") and Path(run_id).name == run_id:
            candidates.append(Path(completion["registry"]) / (run_id + ".json"))
        for candidate in candidates:
            value = _json(candidate)
            if value.get("execution_key") == _plain(record.key) or (
                    not value.get("execution_key") and value.get("run_id") == run_id
                    and receipt.get("worker_run_dir")
                    and value.get("run_dir") == receipt["worker_run_dir"]):
                metadata = value
                break
        raw_tokens = outcome.get("usage")
        if raw_tokens is None:
            raw_tokens = metadata.get("tokens")
            # Registry.start writes empty counters before any parser observation.
            # Those placeholders do not establish measured zero usage.
            if isinstance(raw_tokens, dict) and not any(raw_tokens.values()):
                raw_tokens = None
        tokens = {}
        if isinstance(raw_tokens, dict):
            for name in ("input", "cached_input", "output"):
                try:
                    tokens[name] = max(0, int(raw_tokens.get(name) or 0))
                except (ValueError, TypeError, OverflowError):
                    tokens = {}
                    break
        from .registry_source import _exit_code
        exit_code = _exit_code(outcome.get("backend_exit_code"))
        # Durable unknown/unresolved is never completed merely from sink/mtime.
        status = str(outcome.get("status") or "")
        if exit_code not in (None, 0):
            status = "failed"
        elif status in ("error", "failed", "errored", "cancelled", "timeout", "killed",
                        "capped", "quota_exhausted", "not_logged_in", "not_admitted"):
            pass
        elif status in ("ok", "completed", "done"):
            status = "ok"
        elif record.state == "running":
            status = "running"
        elif record.state == "failed":
            status = "failed"
        else:
            status = "unknown"
        started, ended = to_epoch(record.started_at), to_epoch(record.finished_at)
        if status != "running" and (ended or started) is not None and (ended or started) < cutoff:
            continue
        runs.append(HandRun(
            run_id=run_id, label=str(metadata.get("label") or
                (receipt.get("completion") or {}).get("label") or ""),
            backend=invocation.backend, model=invocation.model, effort=invocation.effort,
            status=status, exit_code=exit_code, parent_session=invocation.parent_session or None,
            tokens=tokens, started_at=started, ended_at=ended,
            pid=None, child_pid=None, lost=False, execution_key=_plain(record.key),
            target_key=attempt.target_key, agent_id=attempt.agent_id,
            thread_id=attempt.thread_id, workspace_id=attempt.workspace_id,
            project_id=attempt.project_id, request_key=attempt.request_key,
            worker_run_dir=str(receipt.get("worker_run_dir") or ""),
            patch_path=str(((record.artifacts.get("finalize") or {}).get("result") or {}).get("patch_path") or ""),
            report_path=str(report.get("report") or ""),
            isolated_cwd=(invocation.isolated_cwd if invocation.isolated_cwd != invocation.source_cwd else ""),
        ))
    return runs


def native_ids(runs):
    return {value for run in runs if run.execution_key
            for value in (run.agent_id, run.thread_id) if value}


def managed_metadata(metadata, runs):
    if metadata.get("id") in native_ids(runs):
        return True
    cwd = metadata.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return False
    isolated = _isolated_roots(runs)
    return bool(isolated) and Path(cwd).resolve() in isolated


# Last (runs list, snapshot of its isolated cwds, resolved set): callers pass the
# same runs list for every session of one build, so resolve its roots once.
_ISOLATED_MEMO: list = [None, None, frozenset()]


def _isolated_roots(runs):
    raw = tuple(run.isolated_cwd for run in runs
                if run.execution_key and run.isolated_cwd
                and Path(run.isolated_cwd).is_absolute())
    if _ISOLATED_MEMO[0] is runs and _ISOLATED_MEMO[1] == raw:
        return _ISOLATED_MEMO[2]
    resolved = frozenset(Path(value).resolve() for value in raw)
    _ISOLATED_MEMO[:] = [runs, raw, resolved]
    return resolved


def dedup_native(sessions, runs):
    """Managed provider thread identities are projection aliases, not new roots."""
    aliases = native_ids(runs)
    sessions[:] = [s for s in sessions if not managed_metadata(
        {"id": s.session_id, "cwd": s.cwd}, runs)]
    for session in sessions:
        session.subagents[:] = [a for a in session.subagents if a.agent_id not in aliases]
