"""`hand-ext run`: pick backend(s), run, record ledger and quota state, summarise."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from . import capacity, codex_usage, go_live, go_usage, isolation, ledger, quota_state, render
from .backends import BackendUnavailable, codex as codex_backend, dsh as dsh_backend
from .backends import get_backend
from .backends.base import Backend, RunSpec, RunState, Status, Usage
from .config import PLUGIN_DIR, ExtConfig
from .constants import (
    AUTO_BACKEND, BROWSER_BACKEND,
    DSH_CAPACITY_MAX_CONTINUATIONS, EXIT_ALL_UNAVAILABLE, EXIT_FAIL, EXIT_USAGE,
    FALLBACK_STATUSES, EXIT_PARALLEL_FULL,
    GO_ESTIMATE_PREFIX, GO_SUMMARY_PREFIX, GO_USAGE_BACKENDS, HAND_RUNS_SUBDIR,
    ISOLATION_WORKTREE, LABEL_MAX_LEN, REPORT_FILE, SECONDS_PER_MINUTE, STATUS_EXIT,
)
from .parallel import ParallelFull, reserve_slot
from .prompt import STDIN_MARK, build_prompt, read_brief
from .run_registry import RunRegistry
from .runner import RunOutcome, run_backend

LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
DEFAULT_LABEL = "hand"
BRIEF_FILE = "brief.md"
PROMPT_FILE = "prompt.md"
META_FILE = "meta.json"
PLUGIN_MANIFEST_RELPATH = ".claude-plugin/plugin.json"


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


def validate_browser(choice: str, browser: bool) -> None:
    if browser and choice not in (AUTO_BACKEND, BROWSER_BACKEND):
        raise ValueError(f"--browser chỉ hỗ trợ backend {BROWSER_BACKEND}, "
                         f"không dùng được với --backend {choice}")


def auto_preflight(cfg: ExtConfig, *, browser: bool = False):
    """Yield (backend-or-None, name, reason) in order, without writing any state."""
    for name in cfg.order:
        if browser and name != BROWSER_BACKEND:
            yield None, name, f"không hỗ trợ --browser (chỉ {BROWSER_BACKEND})"
            continue
        try:
            backend = get_backend(name)
            options = with_sandbox(cfg, name)
        except (BackendUnavailable, ValueError) as exc:
            yield None, name, str(exc)
            continue
        # Alias quota records refer to the same subscription.
        canonical = {"claude-main": "claude-v1", "claude": "claude-v2"}.get(name, name)
        aliases = {"claude-v1": "claude-main", "claude-v2": "claude"}
        until = quota_state.exhausted_until(cfg.quota_state, canonical)
        alias = aliases.get(canonical)
        if until is None and alias:
            until = quota_state.exhausted_until(cfg.quota_state, alias)
        if until is not None:
            yield None, name, f"hết hạn mức tới {quota_state.iso(until)}"
            continue
        try:
            checks = backend.doctor(options)
        except (OSError, ValueError) as exc:
            yield None, name, f"doctor không đọc được cấu hình ({type(exc).__name__})"
            continue
        failed = [check.name for check in checks if check.required and not check.ok]
        if failed:
            # Check names are safe; arbitrary subprocess output can contain credentials.
            yield None, name, f"doctor chưa đạt: {', '.join(failed)} (`hand-ext doctor --backend {name}`)"
            continue
        reason = day_guard(backend, cfg)
        yield (None if reason else backend), name, reason or ""


def iter_candidates(cfg: ExtConfig, choice: str, browser: bool = False) -> Iterator[Backend]:
    validate_browser(choice, browser)
    if choice != AUTO_BACKEND:
        yield get_backend(choice)
        return
    for backend, name, reason in auto_preflight(cfg, browser=browser):
        if backend is None:
            print(f"bỏ qua {name}: {reason}", file=sys.stderr)
        else:
            yield backend


def candidates(cfg: ExtConfig, choice: str, browser: bool = False) -> List[Backend]:
    """Compatibility list API; running consumes the same preflight lazily."""
    return list(iter_candidates(cfg, choice, browser))


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
        browser=bool(getattr(args, "browser", False)),
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


def _write_meta(run_dir: Path, ctx: isolation.IsolationContext, spec: RunSpec,
                backend: str, label: str) -> dict:
    meta = {
        "base_commit": ctx.base_commit, "dirty": ctx.dirty,
        "dirty_files": ctx.dirty_files, "plugin_version": _plugin_version(),
        "backend": backend, "model": spec.model, "label": label,
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
    capacity: bool = False
    go_line: Optional[str] = None
    go_extra: List[str] = field(default_factory=list)


def _new_run_id(label: str, backend: str, attempt: int = 1) -> str:
    base = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{label}-{backend}"
    return base if attempt <= 1 else f"{base}-r{attempt}"


def _prepare_context(cfg: ExtConfig, cwd: Path, choice: isolation.IsolationChoice,
                     run_id: str) -> Tuple[Optional[isolation.IsolationContext], int]:
    run_dir = cfg.runs_dir / run_id
    try:
        return isolation.prepare(cfg, cwd, run_id, run_dir, choice), 0
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
                 run_id: Optional[str] = None, capacity_guard: bool = False,
                 preserve_failed: bool = False) -> _AttemptResult:
    run_id = run_id or _new_run_id(label, backend.name)
    run_dir = cfg.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_run_file(run_dir / BRIEF_FILE, prompt if brief is None else brief)
    _write_run_file(run_dir / PROMPT_FILE, prompt)
    if ctx is None:
        raise isolation.IsolationError("thiếu worktree đã chuẩn bị cho lượt chạy")
    spec = _spec(cfg, args, backend, prompt, ctx.run_cwd, run_id)
    metadata = _write_meta(run_dir, ctx, spec, backend.name, label)
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
    is_cap = False
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
        is_cap = bool(capacity_guard and outcome is not None
                      and capacity.is_capacity_failure(outcome))
        preserve = is_cap or (preserve_failed and (
            outcome is None or outcome.status is not Status.OK))
        do_apply = not no_apply and not fatal and not preserve
        skip_reason = ("không áp sau lỗi" if fatal else
                       "giữ patch do quá tải, không áp về gốc" if is_cap else
                       "lượt chạy tiếp thất bại; giữ patch, không áp về gốc" if preserve
                       else "--no-apply")
        apply_result = isolation.finalize(ctx, run_dir, apply_changes=do_apply,
                                          skip_reason=skip_reason)
        will_cleanup = not keep_worktree and not preserve
        if will_cleanup:
            cleanup_note = isolation.cleanup(ctx, keep=False)
    assert outcome is not None
    entry = _entry(run_id, label, backend.name, spec, started, cwd, outcome)
    ledger.append_entry(cfg.ledger, entry)
    go_line, go_extra = _record_go(cfg, entry, outcome)
    _record_codex(cfg, entry, spec, outcome)
    quota = outcome.state.quota
    exhausted = outcome.status is Status.QUOTA or bool(quota and quota.exhausted)
    if quota is not None or exhausted:
        quota_state.record(cfg.quota_state, backend.name, quota, exhausted)
    code = STATUS_EXIT[outcome.status] if outcome.status not in FALLBACK_STATUSES else -1
    return _AttemptResult(
        code=code, outcome=outcome, spec=spec, run_dir=run_dir, ctx=ctx,
        apply_result=apply_result, entry=entry,
        kept=ctx.mode == ISOLATION_WORKTREE and not will_cleanup,
        cleanup_note=cleanup_note, capacity=is_cap,
        go_line=go_line, go_extra=go_extra)


def _emit(result: _AttemptResult, extra_lines: Optional[List[str]] = None) -> None:
    report = result.run_dir / REPORT_FILE
    isolation.append_report(report, isolation.report_block(
        result.ctx, result.apply_result, kept=result.kept,
        cleanup_note=result.cleanup_note))
    if extra_lines:
        isolation.append_report(report, "\n".join(extra_lines))
    isolation_line = isolation.summary_line(
        result.ctx, result.apply_result, kept=result.kept,
        cleanup_note=result.cleanup_note)
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    print(render.run_summary(result.entry, result.outcome.seconds,
                             str(report) if report.is_file() else None, text,
                             result.outcome.errors, go_line=result.go_line,
                             extra_lines=[*(extra_lines or []), *result.go_extra,
                                          isolation_line]))


def _record_codex(cfg: ExtConfig, entry: dict, spec: RunSpec, outcome: RunOutcome) -> None:
    if entry.get("backend") != codex_backend.NAME:
        return
    windows = outcome.state.extra.get(codex_backend.WINDOWS_EXTRA)
    try:
        codex_usage.record_run(cfg, entry, spec, windows)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"cảnh báo: không ghi được sổ Codex: {exc}", file=sys.stderr)


def _order_fallback(cfg: ExtConfig, args: argparse.Namespace, label: str, cwd: Path,
                    choice: isolation.IsolationChoice, *, brief: str) -> int:
    """Run the original brief through the configured tail after discarding a small patch."""
    remaining = cfg.order[cfg.order.index(dsh_backend.NAME) + 1:] if dsh_backend.NAME in cfg.order else []
    tail = replace(cfg, order=remaining)
    for backend, name, reason in auto_preflight(tail):
        if backend is None:
            print(f"bỏ qua {name}: {reason}", file=sys.stderr)
            continue
        code = _attempt(tail, args, backend, build_prompt(brief, browser=False),
                        label, cwd, choice, brief=brief)
        if code >= 0:
            return code
    return EXIT_ALL_UNAVAILABLE


def _attempt_auto_dsh(cfg: ExtConfig, args: argparse.Namespace, backend: Backend,
                      prompt: str, label: str, cwd: Path,
                      choice: isolation.IsolationChoice, *, brief: str) -> int:
    options = with_sandbox(cfg, backend.name)
    try:
        threshold = dsh_backend.capacity_min_lines(options)
        wait_s = dsh_backend.capacity_wait_seconds(options)
    except ValueError as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    first_id = _new_run_id(label, backend.name)
    ctx, code = _prepare_context(cfg, cwd, choice, first_id)
    if ctx is None:
        return code
    result = _run_attempt(cfg, args, backend, prompt, label, cwd, brief=brief,
                          ctx=ctx, run_id=first_id, capacity_guard=True)
    if not result.capacity:
        _emit(result)
        return result.code
    patch_path = result.apply_result.patch_path
    if ctx.mode != ISOLATION_WORKTREE:
        _emit(result, capacity.report_lines(
            "giữ nguyên dữ liệu (isolation=none)", 0, threshold, wait_s, 0,
            "không đếm được patch dsh; giữ nguyên source, không chạy backend kế tiếp", patch_path))
        return result.code
    if result.apply_result.status == isolation.APPLY_ERROR:
        _emit(result, capacity.report_lines(
            "giữ patch dsh", 0, threshold, wait_s, 0,
            f"lỗi đếm patch: {result.apply_result.detail}; giữ worktree và patch, "
            "không chạy backend kế tiếp", patch_path))
        return result.code
    lines = result.apply_result.changed_lines
    if lines < threshold:
        if getattr(args, "browser", False):
            _emit(result, capacity.report_lines(
                "giữ patch dsh, không chạy codex", lines, threshold, wait_s, 0,
                "codex không hỗ trợ --browser; giữ worktree và patch dsh",
                patch_path))
            print("hand-ext: dsh quá tải và patch nhỏ; codex không hỗ trợ --browser",
                  file=sys.stderr)
            return EXIT_FAIL
        keep = bool(getattr(args, "keep_worktree", False))
        note = isolation.cleanup(ctx, keep=keep)
        result.kept = ctx.mode == ISOLATION_WORKTREE and keep
        result.cleanup_note = note
        result.apply_result.detail = "bỏ patch dsh (dưới ngưỡng), không áp về gốc"
        code = _order_fallback(cfg, args, label, cwd, choice, brief=brief)
        outcome = "ok" if code == 0 else f"mã {code}"
        _emit(result, capacity.report_lines(
            "bỏ patch dsh, chạy lại brief gốc theo order", lines, threshold, wait_s, 0,
            f"backend kế tiếp trong order: {outcome}",
            patch_path))
        return code
    _emit(result, capacity.report_lines(
        "giữ patch dsh, chờ rồi chạy tiếp", lines, threshold, wait_s, 0,
        f"quá tải lần 1/{1 + DSH_CAPACITY_MAX_CONTINUATIONS}, còn "
        f"{DSH_CAPACITY_MAX_CONTINUATIONS} lần chạy tiếp", patch_path))
    continuation_prompt = capacity.continuation_prompt(prompt)
    for continuation in range(1, DSH_CAPACITY_MAX_CONTINUATIONS + 1):
        attempt_id = _new_run_id(label, backend.name, continuation + 1)
        if wait_s > 0:
            print(f"hand-ext: dsh quá tải, giữ patch {lines} dòng; chờ {wait_s}s rồi chạy tiếp "
                  f"({continuation}/{DSH_CAPACITY_MAX_CONTINUATIONS})", file=sys.stderr)
            time.sleep(wait_s)
        else:
            print(f"hand-ext: dsh quá tải, giữ patch {lines} dòng; chạy tiếp không chờ "
                  f"({continuation}/{DSH_CAPACITY_MAX_CONTINUATIONS})", file=sys.stderr)
        retry = _run_attempt(cfg, args, backend, continuation_prompt, label, cwd,
                             brief=brief, ctx=ctx, run_id=attempt_id, capacity_guard=True,
                             preserve_failed=True)
        if not retry.capacity:
            finished = lines if retry.apply_result.status == isolation.APPLY_ERROR \
                else retry.apply_result.changed_lines
            _emit(retry, capacity.report_lines(
                "giữ patch dsh, chờ rồi chạy tiếp", finished, threshold, wait_s,
                continuation,
                f"dsh {retry.outcome.status.value} sau {continuation + 1} lần; "
                "kết thúc nhánh giữ patch", retry.apply_result.patch_path))
            return retry.code if retry.code >= 0 else EXIT_ALL_UNAVAILABLE
        if retry.apply_result.status == isolation.APPLY_ERROR:
            _emit(retry, capacity.report_lines(
                "giữ patch dsh", lines, threshold, wait_s, continuation,
                f"lỗi đếm patch: {retry.apply_result.detail}; giữ worktree và patch",
                retry.apply_result.patch_path))
            return retry.code
        lines = retry.apply_result.changed_lines
        note = ("; số dòng giảm dưới ngưỡng nhưng vẫn giữ nhánh patch, không chuyển codex"
                if lines < threshold else "")
        if continuation < DSH_CAPACITY_MAX_CONTINUATIONS:
            _emit(retry, capacity.report_lines(
                "giữ patch dsh, chờ rồi chạy tiếp", lines, threshold, wait_s,
                continuation, "vẫn quá tải, còn lần chạy tiếp" + note,
                retry.apply_result.patch_path))
            continue
        _emit(retry, capacity.report_lines(
            "giữ patch dsh, chờ rồi chạy tiếp", lines, threshold, wait_s,
            continuation,
            f"vẫn quá tải sau {1 + DSH_CAPACITY_MAX_CONTINUATIONS} lần dsh; "
            "giữ worktree và changes.patch, không áp về gốc" + note,
            retry.apply_result.patch_path))
        return retry.code
    return result.code


def _attempt(cfg: ExtConfig, args: argparse.Namespace, backend: Backend, prompt: str,
             label: str, cwd: Path, choice: isolation.IsolationChoice,
             *, brief: Optional[str] = None) -> int:
    if getattr(args, "backend", None) == AUTO_BACKEND and backend.name == dsh_backend.NAME:
        if brief is None:
            brief = prompt
        return _attempt_auto_dsh(cfg, args, backend, prompt, label, cwd, choice, brief=brief)
    run_id = _new_run_id(label, backend.name)
    ctx, code = _prepare_context(cfg, cwd, choice, run_id)
    if ctx is None:
        return code
    result = _run_attempt(cfg, args, backend, prompt, label, cwd, brief=brief,
                          ctx=ctx, run_id=run_id, capacity_guard=False)
    _emit(result)
    return result.code


def _record_go(cfg: ExtConfig, entry: dict,
               outcome: RunOutcome) -> Tuple[Optional[str], List[str]]:
    """Write the Go ledger, then prefer the real statusline numbers over the estimate.

    A logging or live-fetch failure warns/degrades, never fails the run.
    """
    if entry.get("backend") not in GO_USAGE_BACKENDS:
        return None, []
    try:
        summary = go_usage.record_run(cfg, entry,
                                      outcome.state.extra.get("go_allowance_usd"))
    except OSError as exc:
        print(f"cảnh báo: không ghi được sổ Go: {exc}", file=sys.stderr)
        return None, []
    estimated = go_usage.summary_line(summary)
    live = go_live.refresh_and_read(cfg.go_usage_live, os.environ)
    if live is None:
        return estimated, []
    extra = []
    if estimated and estimated.startswith(GO_SUMMARY_PREFIX):
        extra.append(GO_ESTIMATE_PREFIX + estimated[len(GO_SUMMARY_PREFIX):])
    return go_live.live_line(live, time.time()), extra


def cmd_run(cfg: ExtConfig, args: argparse.Namespace) -> int:
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
    browser = bool(getattr(args, "browser", False))
    validate_browser(args.backend, browser)
    brief = read_brief(args.brief)
    prompt = build_prompt(brief, browser=browser)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    label = safe_label(args)
    try:
        choice = isolation.resolve_choice(cfg, cwd, getattr(args, "isolation", None))
    except isolation.IsolationError as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if choice.warning:
        print(f"hand-ext: {choice.warning}", file=sys.stderr)
    for backend in iter_candidates(cfg, args.backend, browser=browser):
        reason = day_guard(backend, cfg) if args.backend != AUTO_BACKEND else None
        if reason:
            print(f"hand-ext: {reason}", file=sys.stderr)
            if args.backend != AUTO_BACKEND:
                return EXIT_ALL_UNAVAILABLE
            continue
        code = _attempt(cfg, args, backend, prompt, label, cwd, choice, brief=brief)
        if code >= 0:
            return code
        if args.backend != AUTO_BACKEND:
            break
        print(f"{backend.name} hết hạn mức/chưa đăng nhập; thử backend kế tiếp",
              file=sys.stderr)
    print("Không backend nào chạy được (hết hạn mức hoặc chưa đăng nhập).", file=sys.stderr)
    return EXIT_ALL_UNAVAILABLE


def last_run(cfg: ExtConfig, name: str) -> Optional[dict]:
    runs = [e for e in ledger.read_entries(cfg.ledger) if e.get("backend") == name]
    return runs[-1] if runs else None
