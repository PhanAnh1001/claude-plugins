"""`hand-ext run`: pick backend(s), run, record ledger and quota state, summarise."""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import go_usage, isolation, ledger, quota_state, render
from .backends import BackendUnavailable, get_backend
from .backends.base import Backend, RunSpec, RunState, Status, Usage
from .config import ExtConfig
from .constants import (
    AUTO_BACKEND, BROWSER_BACKEND, EXIT_ALL_UNAVAILABLE, EXIT_USAGE, FALLBACK_STATUSES,
    GO_USAGE_BACKENDS, HAND_RUNS_SUBDIR, LABEL_MAX_LEN, REPORT_FILE, SECONDS_PER_MINUTE,
    STATUS_EXIT,
)
from .prompt import STDIN_MARK, build_prompt, read_brief
from .run_registry import RunRegistry
from .runner import RunOutcome, run_backend

LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
DEFAULT_LABEL = "hand"


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


def validate_browser(choice: str, browser: bool) -> None:
    if browser and choice not in (AUTO_BACKEND, BROWSER_BACKEND):
        raise ValueError(f"--browser chỉ hỗ trợ backend {BROWSER_BACKEND}, "
                         f"không dùng được với --backend {choice}")


def _browser_order(cfg: ExtConfig) -> List[str]:
    for name in cfg.order:
        if name != BROWSER_BACKEND:
            print(f"bỏ qua {name}: không hỗ trợ --browser (chỉ {BROWSER_BACKEND})",
                  file=sys.stderr)
    return [BROWSER_BACKEND]


def candidates(cfg: ExtConfig, choice: str, browser: bool = False) -> List[Backend]:
    validate_browser(choice, browser)
    if choice != AUTO_BACKEND:
        return [get_backend(choice)]
    found: List[Backend] = []
    for name in _browser_order(cfg) if browser else cfg.order:
        try:
            backend = get_backend(name)
        except BackendUnavailable as exc:
            print(f"bỏ qua {name}: {exc}", file=sys.stderr)
            continue
        until = quota_state.exhausted_until(cfg.quota_state, name)
        if until is not None:
            print(f"bỏ qua {name}: hết hạn mức tới {quota_state.iso(until)}", file=sys.stderr)
        elif not backend_ready(backend, cfg):
            print(f"bỏ qua {name}: doctor chưa đạt (`hand-ext doctor --backend {name}`)",
                  file=sys.stderr)
        else:
            found.append(backend)
    return found


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


def _attempt(cfg: ExtConfig, args: argparse.Namespace, backend: Backend, prompt: str,
             label: str, cwd: Path, choice: isolation.IsolationChoice) -> int:
    run_id = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{label}-{backend.name}"
    run_dir = cfg.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        ctx = isolation.prepare(cfg, cwd, run_id, run_dir, choice)
    except isolation.IsolationError as exc:
        isolation.append_report(run_dir / REPORT_FILE, isolation.failure_block(str(exc)))
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    spec = _spec(cfg, args, backend, prompt, ctx.run_cwd, run_id)
    started = _now()
    registry = RunRegistry(
        cfg.machine_state_dir / HAND_RUNS_SUBDIR, run_id, label, backend.name,
        spec.model, cwd, spec.run_dir)
    registry.start()
    no_apply = bool(getattr(args, "no_apply", False))
    keep_worktree = bool(getattr(args, "keep_worktree", False))
    apply_result = isolation.ApplyResult()
    cleanup_note = ""
    fatal = False
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
        apply_result = isolation.finalize(
            ctx, run_dir, apply_changes=not no_apply and not fatal,
            skip_reason="không áp sau lỗi" if fatal else "--no-apply")
        if not keep_worktree:
            cleanup_note = isolation.cleanup(ctx, keep=False)
        isolation.append_report(run_dir / REPORT_FILE, isolation.report_block(
            ctx, apply_result, kept=keep_worktree, cleanup_note=cleanup_note))
        isolation_line = isolation.summary_line(
            ctx, apply_result, kept=keep_worktree, cleanup_note=cleanup_note)
    entry = _entry(run_id, label, backend.name, spec, started, cwd, outcome)
    ledger.append_entry(cfg.ledger, entry)
    go_line = _record_go(cfg, entry, outcome)
    quota = outcome.state.quota
    exhausted = outcome.status is Status.QUOTA or bool(quota and quota.exhausted)
    if quota is not None or exhausted:
        quota_state.record(cfg.quota_state, backend.name, quota, exhausted)
    report = spec.run_dir / REPORT_FILE
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    print(render.run_summary(entry, outcome.seconds, str(report) if report.is_file() else None,
                             text, outcome.errors, go_line=go_line,
                             extra_lines=[isolation_line]))
    return STATUS_EXIT[outcome.status] if outcome.status not in FALLBACK_STATUSES else -1


def _record_go(cfg: ExtConfig, entry: dict, outcome: RunOutcome) -> Optional[str]:
    """Write the machine-wide Go ledger/summary; a logging failure warns, never fails the run."""
    if entry.get("backend") not in GO_USAGE_BACKENDS:
        return None
    try:
        summary = go_usage.record_run(cfg, entry,
                                      outcome.state.extra.get("go_allowance_usd"))
    except OSError as exc:
        print(f"cảnh báo: không ghi được sổ Go: {exc}", file=sys.stderr)
        return None
    return go_usage.summary_line(summary)


def cmd_run(cfg: ExtConfig, args: argparse.Namespace) -> int:
    browser = bool(getattr(args, "browser", False))
    validate_browser(args.backend, browser)
    prompt = build_prompt(read_brief(args.brief), browser=browser)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    label = safe_label(args)
    try:
        choice = isolation.resolve_choice(cfg, cwd, getattr(args, "isolation", None))
    except isolation.IsolationError as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if choice.warning:
        print(f"hand-ext: {choice.warning}", file=sys.stderr)
    backends = candidates(cfg, args.backend, browser=browser)
    for index, backend in enumerate(backends):
        code = _attempt(cfg, args, backend, prompt, label, cwd, choice)
        if code >= 0:
            return code
        if args.backend != AUTO_BACKEND:
            break
        if index + 1 < len(backends):
            print(f"{backend.name} hết hạn mức/chưa đăng nhập; thử backend kế tiếp",
                  file=sys.stderr)
    print("Không backend nào chạy được (hết hạn mức hoặc chưa đăng nhập).", file=sys.stderr)
    return EXIT_ALL_UNAVAILABLE


def last_run(cfg: ExtConfig, name: str) -> Optional[dict]:
    runs = [e for e in ledger.read_entries(cfg.ledger) if e.get("backend") == name]
    return runs[-1] if runs else None
