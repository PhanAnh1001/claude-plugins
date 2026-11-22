"""`hand-ext run`: pick backend(s), run, record ledger and quota state, summarise."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from . import codex_usage, gc, isolation, ledger, quota_state, render
from .backends import BackendUnavailable, codex as codex_backend
from .backends import get_backend
from .backends.base import Backend, RunSpec, RunState, Status, Usage
from .config import PLUGIN_DIR, ExtConfig
from .constants import (
    AUTO_BACKEND, CHANGES_PATCH_FILE, EXIT_ALL_UNAVAILABLE, EXIT_USAGE, EXIT_PARALLEL_FULL,
    HAND_RUNS_SUBDIR,
    ISOLATION_WORKTREE, LABEL_MAX_LEN, REPORT_FILE, SECONDS_PER_MINUTE, STATUS_EXIT,
)
from .parallel import ParallelFull, reserve_slot
from .prompt import STDIN_MARK, build_prompt, read_brief
from .run_registry import RunRegistry
from .runner import RunOutcome, run_backend

LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
RUN_ATTEMPT_RE = re.compile(r"-r(\d+)$")  # suffix written by _new_run_id for retries
ESCALATED_TIER = 2  # escalation always lands on the higher collect/chrome tier
DEFAULT_LABEL = "hand"
BRIEF_FILE = "brief.md"
PROMPT_FILE = "prompt.md"
META_FILE = "meta.json"
PLUGIN_MANIFEST_RELPATH = ".claude-plugin/plugin.json"
# Without --role or an explicit --backend there is nothing to pick (no automatic order).
BACKEND_REQUIRED = "cần --role code|collect|chrome hoặc --backend <tên>"
# Quota/not-logged-in on the chosen backend: report it, never switch backend or account.
UNAVAILABLE_NOTE = "{name} hết hạn mức hoặc chưa đăng nhập; không tự chuyển backend"


def safe_label(args: argparse.Namespace) -> str:
    raw = args.label or (Path(args.brief).stem if args.brief != STDIN_MARK else DEFAULT_LABEL)
    return LABEL_SAFE_RE.sub("-", raw).strip("-")[:LABEL_MAX_LEN] or DEFAULT_LABEL


def backend_ready(backend: Backend, cfg: ExtConfig) -> bool:
    return all(c.ok or not c.required
               for c in backend.doctor(with_sandbox(cfg, backend.name)))


def with_sandbox(cfg: ExtConfig, name: str) -> dict:
    options = cfg.options(name)
    options.setdefault("sandbox", cfg.sandbox)
    return options


def day_guard(backend: Backend, cfg: ExtConfig) -> Optional[str]:
    """Per-account daily guard; None means the run may start."""
    guard = getattr(backend, "day_block_reason", None)
    return guard(with_sandbox(cfg, backend.name)) if callable(guard) else None


def missing_backend(args: argparse.Namespace) -> Optional[str]:
    """Usage error when neither --role nor an explicit backend chose one."""
    return BACKEND_REQUIRED if getattr(args, "backend", None) in (None, AUTO_BACKEND) else None


def preflight(cfg: ExtConfig, name: str) -> Tuple[Optional[Backend], str]:
    """(backend, "") when `name` may start now, else (None, reason); writes no state."""
    try:
        backend = get_backend(name)
        options = with_sandbox(cfg, name)
    except (BackendUnavailable, ValueError) as exc:
        return None, str(exc)
    # Alias quota records refer to the same subscription.
    canonical = {"claude-main": "claude-v1", "claude": "claude-v2"}.get(name, name)
    aliases = {"claude-v1": "claude-main", "claude-v2": "claude"}
    until = quota_state.exhausted_until(cfg.quota_state, canonical)
    alias = aliases.get(canonical)
    if until is None and alias:
        until = quota_state.exhausted_until(cfg.quota_state, alias)
    if until is not None:
        return None, f"hết hạn mức tới {quota_state.iso(until)}"
    try:
        checks = backend.doctor(options)
    except (OSError, ValueError) as exc:
        return None, f"doctor không đọc được cấu hình ({type(exc).__name__})"
    failed = [check.name for check in checks if check.required and not check.ok]
    if failed:
        # Check names are safe; arbitrary subprocess output can contain credentials.
        return None, f"doctor chưa đạt: {', '.join(failed)} (`hand-ext doctor --backend {name}`)"
    reason = day_guard(backend, cfg)
    return (None, reason) if reason else (backend, "")


# Role whose hand needs the Claude in Chrome tools.
CHROME_ROLE = "chrome"


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _spec(cfg: ExtConfig, args: argparse.Namespace, backend: Backend, prompt: str,
          run_cwd: Path, run_id: str) -> RunSpec:
    options = with_sandbox(cfg, backend.name)
    max_tokens = args.max_tokens if args.max_tokens is not None else cfg.max_tokens
    return RunSpec(
        prompt=prompt, cwd=run_cwd, run_dir=cfg.runs_dir / run_id,
        model=args.model or str(options.get("model", "")),
        effort=args.effort or str(options.get("effort", options.get("variant", ""))),
        sandbox=args.sandbox or cfg.sandbox,
        timeout_s=int((args.timeout_min or cfg.timeout_min) * SECONDS_PER_MINUTE),
        max_tokens=max_tokens, options=options,
        chrome=getattr(args, "role", None) == CHROME_ROLE,
    )


def _entry(run_id: str, label: str, backend: str, spec: RunSpec, started: str,
           cwd: Path, outcome: RunOutcome) -> dict:
    usage, quota = outcome.state.usage, outcome.state.quota
    return {
        "run_id": run_id, "label": label, "backend": backend, "model": spec.model,
        "effort": spec.effort, "started": started, "ended": _now(), "cwd": str(cwd),
        "status": outcome.status.value, "exit_code": outcome.exit_code,
        "tokens": {"input": usage.input, "cached_input": usage.cached_input,
                   "output": usage.output},
        "quota": {"used_percent": quota.used_percent if quota else None,
                  "resets_at": quota.resets_at if quota else None},
    }


def _write_run_file(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"cảnh báo: không ghi được {path}: {exc}", file=sys.stderr)


def _plugin_version() -> Optional[str]:
    try:
        data = json.loads((PLUGIN_DIR / PLUGIN_MANIFEST_RELPATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def _attempt_number(run_id: str) -> Optional[int]:
    match = RUN_ATTEMPT_RE.search(run_id)
    return int(match.group(1)) if match else None


def _role_fields(args: argparse.Namespace, run_id: str) -> dict:
    """Profile role/tier trail appended to meta and ledger; defaults when no --role."""
    return {"role": getattr(args, "role", None) or "", "tier": getattr(args, "tier", None),
            "attempt": _attempt_number(run_id),
            "escalated_from": getattr(args, "escalated_from", None)}


def apply_role(cfg: ExtConfig, args: argparse.Namespace) -> Optional[str]:
    """Resolve --role into backend/model/effort on args; return a usage error or None."""
    role = getattr(args, "role", None)
    tier = getattr(args, "tier", None)
    escalated = getattr(args, "escalated_from", None)
    if role is None:
        return "--tier/--escalated-from cần --role" if tier is not None or escalated else None
    if escalated and tier != ESCALATED_TIER:
        return f"--escalated-from chỉ dùng với --tier {ESCALATED_TIER}"
    from shared_config import load_config as load_shared
    from .profile_cmd import backend_name
    from .profiles import ProfileError, role_spec
    try:
        spec = role_spec(load_shared(Path(args.cwd) if args.cwd else cfg.root).effective,
                         role, tier)
    except ProfileError as exc:
        return str(exc)
    backend = backend_name(spec)
    if args.backend not in (None, AUTO_BACKEND, backend):
        return f"--backend {args.backend} lệch vai {role} ({backend})"
    args.backend = backend
    args.model = args.model or spec["model"]
    args.effort = args.effort or spec["effort"]
    args.tier = spec["tier"]  # record the resolved tier (collect/chrome default to 1)
    return None


def _write_meta(run_dir: Path, ctx: isolation.IsolationContext, spec: RunSpec,
                backend: str, label: str, extra: Optional[dict] = None) -> dict:
    meta = {
        "base_commit": ctx.base_commit, "dirty": ctx.dirty,
        "worktree": str(ctx.worktree) if ctx.worktree else None,
        "dirty_files": ctx.dirty_files, "plugin_version": _plugin_version(),
        "backend": backend, "model": spec.model, "label": label,
        "effort": spec.effort, **(extra or {}),
    }
    return meta


@dataclass
class _AttemptResult:
    code: int
    outcome: RunOutcome
    spec: RunSpec
    run_dir: Path
    ctx: isolation.IsolationContext
    apply_result: isolation.ApplyResult
    entry: dict
    kept: bool
    cleanup_note: str = ""


def _new_run_id(label: str, backend: str, attempt: int = 1) -> str:
    base = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{label}-{backend}"
    return base if attempt <= 1 else f"{base}-r{attempt}"


def _prepare_context(cfg: ExtConfig, cwd: Path, choice: isolation.IsolationChoice,
                     run_id: str, backend: str = "") -> Tuple[Optional[isolation.IsolationContext], int]:
    run_dir = cfg.runs_dir / run_id
    try:
        return isolation.prepare(cfg, cwd, run_id, run_dir, choice, backend=backend), 0
    except isolation.IsolationError as exc:
        isolation.append_report(run_dir / REPORT_FILE, isolation.failure_block(str(exc)))
        print(f"hand-ext: {exc}", file=sys.stderr)
        return None, EXIT_USAGE


def _resolve_parent_session(cfg: ExtConfig) -> Optional[str]:
    """Map runtime thread/agent ids to the side state's canonical session uuid."""
    thread = os.environ.get("CODEX_THREAD_ID")
    agent = os.environ.get("PASEO_AGENT_ID")
    if thread or agent:
        from hh_ps.registry_source import load_ps_config
        from side_session.state import load_all
        try:
            states = load_all(load_ps_config(cfg.root).side_state_dir)
        except (OSError, ValueError, TypeError, KeyError):
            states = []
        for state in states:
            if ((thread and thread in (state.uuid, state.codex_thread_id)) or
                    (agent and agent in (state.uuid, state.paseo_agent_id))):
                return state.uuid
    return thread or os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def _run_attempt(cfg: ExtConfig, args: argparse.Namespace, backend: Backend, prompt: str,
                 label: str, cwd: Path, *, brief: Optional[str] = None,
                 ctx: Optional[isolation.IsolationContext] = None,
                 run_id: Optional[str] = None) -> _AttemptResult:
    run_id = run_id or _new_run_id(label, backend.name)
    run_dir = cfg.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_run_file(run_dir / BRIEF_FILE, prompt if brief is None else brief)
    _write_run_file(run_dir / PROMPT_FILE, prompt)
    if ctx is None:
        raise isolation.IsolationError("thiếu worktree đã chuẩn bị cho lượt chạy")
    spec = _spec(cfg, args, backend, prompt, ctx.run_cwd, run_id)
    metadata = _write_meta(run_dir, ctx, spec, backend.name, label,
                           _role_fields(args, run_id))
    started = _now()
    registry = RunRegistry(
        cfg.machine_state_dir / HAND_RUNS_SUBDIR, run_id, label, backend.name,
        spec.model, cwd, spec.run_dir, parent_session=_resolve_parent_session(cfg),
        effort=spec.effort, metadata=metadata)
    registry.start()
    no_apply = bool(getattr(args, "no_apply", False))
    keep_worktree = bool(getattr(args, "keep_worktree", False))
    apply_result = isolation.ApplyResult()
    cleanup_note = ""
    fatal = False
    outcome: Optional[RunOutcome] = None
    try:
        try:
            outcome = run_backend(backend, spec, registry=registry)
        except OSError as exc:
            outcome = RunOutcome(Status.FAILED, None, RunState(usage=Usage()), 0.0,
                                 [f"không chạy được {backend.name}: {exc}"])
            registry.finish(outcome.status.value, None, outcome.state.usage)
        except BaseException:
            registry.finish(Status.FAILED.value, None, None)
            fatal = True
            raise
        else:
            registry.finish(outcome.status.value, outcome.exit_code, outcome.state.usage)
    finally:
        do_apply = not no_apply and not fatal
        skip_reason = "không áp sau lỗi" if fatal else "--no-apply"
        apply_result = isolation.finalize(ctx, run_dir, apply_changes=do_apply,
                                          skip_reason=skip_reason)
        will_cleanup = not keep_worktree
        if will_cleanup and ctx.worktree is not None:
            from .worktree_lifecycle import remove_preserved, record
            cleanup_note = remove_preserved(ctx, apply_result, run_dir)
            will_cleanup = not cleanup_note
            record(registry.path, cleanup="removed" if will_cleanup else "retained")
        elif not keep_worktree:
            will_cleanup, cleanup_note = _release_saved_worktree(ctx, run_dir, apply_result)

    assert outcome is not None
    entry = {**_entry(run_id, label, backend.name, spec, started, cwd, outcome),
             **_role_fields(args, run_id)}
    ledger.append_entry(cfg.ledger, entry)
    _record_codex(cfg, entry, spec, outcome)
    quota = outcome.state.quota
    exhausted = outcome.status is Status.QUOTA or bool(quota and quota.exhausted)
    if quota is not None or exhausted:
        quota_state.record(cfg.quota_state, backend.name, quota, exhausted)
    return _AttemptResult(
        code=STATUS_EXIT[outcome.status], outcome=outcome, spec=spec, run_dir=run_dir,
        ctx=ctx, apply_result=apply_result, entry=entry,
        kept=ctx.mode == ISOLATION_WORKTREE and not will_cleanup,
        cleanup_note=cleanup_note)


def _release_saved_worktree(ctx: isolation.IsolationContext, run_dir: Path,
                            apply_result: isolation.ApplyResult) -> Tuple[bool, str]:
    """Remove a failed run's worktree only once changes.patch provably holds its changes."""
    if (ctx.mode != ISOLATION_WORKTREE or ctx.worktree is None
            or apply_result.status == isolation.APPLY_ERROR
            or not gc.patch_matches_worktree(ctx.worktree, ctx.base_commit,
                                             run_dir / CHANGES_PATCH_FILE,
                                             started_clean=not ctx.dirty)):
        return False, ""
    note = isolation.cleanup(ctx, keep=False)
    return not note, note


def _emit(result: _AttemptResult) -> None:
    report = result.run_dir / REPORT_FILE
    isolation.append_report(report, isolation.report_block(
        result.ctx, result.apply_result, kept=result.kept,
        cleanup_note=result.cleanup_note, keep_reason=("lỗi" if result.outcome.status is not Status.OK else
                     "--keep-worktree" if result.kept and not result.cleanup_note else "")))
    isolation_line = isolation.summary_line(
        result.ctx, result.apply_result, kept=result.kept,
        cleanup_note=result.cleanup_note)
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    print(render.run_summary(result.entry, result.outcome.seconds,
                             str(report) if report.is_file() else None, text,
                             result.outcome.errors, extra_lines=[isolation_line]))


def _record_codex(cfg: ExtConfig, entry: dict, spec: RunSpec, outcome: RunOutcome) -> None:
    if entry.get("backend") != codex_backend.NAME:
        return
    windows = outcome.state.extra.get(codex_backend.WINDOWS_EXTRA)
    try:
        codex_usage.record_run(cfg, entry, spec, windows)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"cảnh báo: không ghi được sổ Codex: {exc}", file=sys.stderr)


def _attempt(cfg: ExtConfig, args: argparse.Namespace, backend: Backend, prompt: str,
             label: str, cwd: Path, choice: isolation.IsolationChoice,
             *, brief: Optional[str] = None) -> int:
    run_id = _new_run_id(label, backend.name)
    ctx, code = _prepare_context(cfg, cwd, choice, run_id, backend.name)
    if ctx is None:
        return code
    result = _run_attempt(cfg, args, backend, prompt, label, cwd, brief=brief,
                          ctx=ctx, run_id=run_id)
    _emit(result)
    return result.code


def cmd_run(cfg: ExtConfig, args: argparse.Namespace) -> int:
    role_error = apply_role(cfg, args) or missing_backend(args)
    if role_error:
        print(f"hand-ext run: {role_error}", file=sys.stderr)
        return EXIT_USAGE
    mode = getattr(args, "mode", None) or getattr(cfg, "mode", "shell")
    if mode != "shell":
        from .paseo_controller import cmd_managed_run
        return cmd_managed_run(cfg, args, mode=mode)
    return _cmd_shell_run(cfg, args)


def _cmd_shell_run(cfg: ExtConfig, args: argparse.Namespace) -> int:
    with ExitStack() as slots:
        try:
            slots.enter_context(reserve_slot(cfg.root, cfg.max_parallel))
        except ParallelFull as exc:
            print(f"hand-ext: {exc}", file=sys.stderr)
            return EXIT_PARALLEL_FULL
        except OSError as exc:
            print(f"hand-ext: không khóa được slot hand: {exc}", file=sys.stderr)
            return EXIT_USAGE
        return _cmd_run(cfg, args)


def _cmd_run(cfg: ExtConfig, args: argparse.Namespace) -> int:
    brief = read_brief(args.brief)
    prompt = build_prompt(brief)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    label = safe_label(args)
    try:
        choice = isolation.resolve_choice(cfg, cwd, getattr(args, "isolation", None))
    except isolation.IsolationError as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if choice.warning:
        print(f"hand-ext: {choice.warning}", file=sys.stderr)
    backend = get_backend(args.backend)
    reason = day_guard(backend, cfg)
    if reason:
        print(f"hand-ext: {reason}", file=sys.stderr)
        return EXIT_ALL_UNAVAILABLE
    code = _attempt(cfg, args, backend, prompt, label, cwd, choice, brief=brief)
    if code == EXIT_ALL_UNAVAILABLE:
        print(UNAVAILABLE_NOTE.format(name=backend.name), file=sys.stderr)
    return code


def last_run(cfg: ExtConfig, name: str) -> Optional[dict]:
    runs = [e for e in ledger.read_entries(cfg.ledger) if e.get("backend") == name]
    return runs[-1] if runs else None
