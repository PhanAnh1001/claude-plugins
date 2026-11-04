"""hand-gpt command line: setup, doctor, estimate, run, report."""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import ledger, render
from .codex_runner import RunResult, RunSpec, run_codex
from .config import HandConfig, load_config
from .pricing import Tokens
from .constants import (
    CHARS_PER_TOKEN, EFFORTS, EXIT_NEEDS_APPROVAL, EXIT_OK, EXIT_USAGE, LABEL_MAX_LEN,
    PREAMBLE_RELPATH, SANDBOXES, STANDARD_TIER, STATUS_EXIT, Status,
)
from .setup_doctor import login_hint, run_doctor, run_setup

PLUGIN_DIR = Path(__file__).resolve().parents[2]
SECONDS_PER_MINUTE = 60
LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
DEFAULT_LABEL = "hand"
STDIN_MARK = "-"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hand-gpt", description="Chạy GPT qua codex exec làm hand cho brain.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="tạo CODEX_HOME và khoá mặc định Flex").add_argument("--cwd")
    sub.add_parser("doctor", help="kiểm codex, config, đăng nhập, sổ").add_argument("--cwd")
    for name in ("estimate", "run"):
        s = sub.add_parser(name)
        s.add_argument("--brief", required=True, help="file brief hoặc - cho stdin")
        s.add_argument("--label")
        s.add_argument("--cwd")
        s.add_argument("--effort", choices=EFFORTS)
        s.add_argument("--max-usd", type=float)
        if name == "run":
            s.add_argument("--timeout-min", type=float)
            s.add_argument("--sandbox", choices=SANDBOXES)
            s.add_argument("--approved", action="store_true")
            s.add_argument("--allow-standard", action="store_true")
    r = sub.add_parser("report")
    r.add_argument("--since", help="YYYY-MM-DD")
    r.add_argument("--label")
    r.add_argument("--cwd")
    return p


def _cfg(args: argparse.Namespace) -> HandConfig:
    return load_config(Path(args.cwd) if args.cwd else None)


def _read_brief(src: str) -> str:
    return sys.stdin.read() if src == STDIN_MARK else Path(src).read_text(encoding="utf-8")


def build_prompt(brief: str) -> str:
    preamble = (PLUGIN_DIR / PREAMBLE_RELPATH).read_text(encoding="utf-8")
    return f"{preamble.rstrip()}\n\n---\n\n# BRIEF\n\n{brief.strip()}\n"


def _label(args: argparse.Namespace) -> str:
    raw = args.label or (Path(args.brief).stem if args.brief != STDIN_MARK else DEFAULT_LABEL)
    return LABEL_SAFE_RE.sub("-", raw).strip("-")[:LABEL_MAX_LEN] or DEFAULT_LABEL


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    changed, path = run_setup(cfg)
    print(f"{'đã ghi' if changed else 'không đổi'}: {path}")
    print("Đăng nhập bằng API key (tự chạy trong terminal riêng, dán key khi được hỏi):")
    print(f"  {login_hint(cfg)}")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(_cfg(args))
    print("| kiểm | kết quả | chi tiết |\n|---|---|---|")
    for c in checks:
        print(f"| {c.name} | {'đạt' if c.ok else 'thiếu'} | {c.detail} |")
    return EXIT_OK if all(c.ok for c in checks) else 1


def cmd_estimate(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    prompt = build_prompt(_read_brief(args.brief))
    print(render.estimate_table(
        model=cfg.model, tier=cfg.service_tier, effort=args.effort or cfg.effort,
        label=_label(args), max_usd=_max_usd(args, cfg), approval_usd=cfg.approval_usd,
        brief_tokens=len(prompt) // CHARS_PER_TOKEN, spent_usd=ledger.total_usd(cfg.ledger),
        prices=cfg.prices,
    ))
    return EXIT_OK


def _max_usd(args: argparse.Namespace, cfg: HandConfig) -> float:
    return args.max_usd if args.max_usd is not None else cfg.max_usd


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _record(cfg: HandConfig, run_id: str, label: str, spec: RunSpec, started: str,
            result: RunResult, approved: bool) -> None:
    ledger.append_entry(cfg.ledger, {
        "run_id": run_id, "label": label, "started": started, "ended": _now(),
        "cwd": str(spec.cwd), "model": spec.model, "tier": spec.tier, "effort": spec.effort,
        "status": result.status.value, "exit_code": result.exit_code,
        "tokens": result.tokens.to_dict(), "usd": round(result.usd, 6),
        "max_usd": spec.max_usd, "approved": approved,
    })


def _one_run(cfg: HandConfig, args: argparse.Namespace, prompt: str, label: str,
             tier: str, max_usd: float, cwd: Path) -> RunResult:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "" if tier == cfg.service_tier else f"-{tier}"
    run_id = f"{stamp}-{label}{suffix}"
    spec = RunSpec(
        prompt=prompt, cwd=cwd, run_dir=cfg.runs_dir / run_id, codex_home=cfg.codex_home,
        model=cfg.model, tier=tier, effort=args.effort or cfg.effort,
        sandbox=args.sandbox or cfg.sandbox, max_usd=max_usd,
        timeout_s=(args.timeout_min or cfg.timeout_min) * SECONDS_PER_MINUTE, prices=cfg.prices,
    )
    started = _now()
    try:
        result = run_codex(spec)
    except OSError as exc:
        result = RunResult(Status.FAILED, None, Tokens(),
                           0.0, 0.0, errors=[f"không chạy được codex: {exc}"])
    _record(cfg, run_id, label, spec, started, result, args.approved)
    return result


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    max_usd = _max_usd(args, cfg)
    if max_usd >= cfg.approval_usd and not args.approved:
        print(f"Từ chối: trần {max_usd} USD ≥ ngưỡng duyệt {cfg.approval_usd} USD; "
              "báo bảng (`hand-gpt estimate`), chờ người dùng đồng ý rồi thêm --approved.",
              file=sys.stderr)
        return EXIT_NEEDS_APPROVAL
    prompt = build_prompt(_read_brief(args.brief))
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    label = _label(args)
    result = _one_run(cfg, args, prompt, label, cfg.service_tier, max_usd, cwd)
    if result.status is Status.FLEX_REJECTED and args.allow_standard:
        remaining = max_usd - result.usd
        print(f"Flex bị từ chối; chạy lại tầng Standard (--allow-standard), trần còn {remaining:.4f} USD",
              file=sys.stderr)
        result = _one_run(cfg, args, prompt, label, STANDARD_TIER, remaining, cwd)
    report_text = result.report_path.read_text(encoding="utf-8") if result.report_path else ""
    print(render.run_summary(
        status=result.status.value, usd=result.usd, tokens=result.tokens.to_dict(),
        seconds=result.seconds, report_path=str(result.report_path) if result.report_path else None,
        report_text=report_text, errors=result.errors,
    ))
    return STATUS_EXIT[result.status]


def cmd_report(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    entries = ledger.read_entries(cfg.ledger) if cfg.ledger.is_file() else []
    if args.since:
        entries = [e for e in entries if str(e.get("started", ""))[:10] >= args.since]
    if args.label:
        entries = [e for e in entries if e.get("label") == args.label]
    print(render.ledger_report(entries))
    return EXIT_OK


COMMANDS = {"setup": cmd_setup, "doctor": cmd_doctor, "estimate": cmd_estimate,
            "run": cmd_run, "report": cmd_report}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except (OSError, ValueError) as exc:
        print(f"hand-gpt: {exc}", file=sys.stderr)
        return EXIT_USAGE
