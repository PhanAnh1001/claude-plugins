"""hand-ext command line: setup, doctor, run, status, report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import ledger, quota_state, render
from .backends import BackendUnavailable, KNOWN_BACKENDS, get_backend
from .backends.base import Check
from .config import ExtConfig, load_config
from .constants import ALL_BACKENDS, AUTO_BACKEND, EXIT_FAIL, EXIT_OK, EXIT_USAGE, SANDBOXES
from .run_cmd import backend_ready, cmd_run, last_run, with_sandbox


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hand-ext", description="Chạy hand ngoài qua CLI đăng nhập gói subscription (không API).")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("setup", "ghi cấu hình CLI, in lệnh đăng nhập gói"),
                       ("doctor", "kiểm cài đặt, đăng nhập gói, cấu hình")):
        s = sub.add_parser(name, help=text)
        s.add_argument("--backend", default=ALL_BACKENDS)
        s.add_argument("--cwd")
    r = sub.add_parser("run", help="chạy một brief")
    r.add_argument("--brief", required=True, help="file brief hoặc - cho stdin")
    r.add_argument("--backend", default=AUTO_BACKEND)
    for flag in ("--label", "--cwd", "--model", "--effort"):
        r.add_argument(flag)
    r.add_argument("--timeout-min", type=float)
    r.add_argument("--max-tokens", type=int)
    r.add_argument("--sandbox", choices=SANDBOXES)
    sub.add_parser("status", help="sẵn sàng, hạn mức, lượt gần nhất").add_argument("--cwd")
    rep = sub.add_parser("report", help="tổng lượt và token")
    for flag in ("--since", "--backend", "--label", "--cwd"):
        rep.add_argument(flag)
    return p


def _cfg(args: argparse.Namespace) -> ExtConfig:
    return load_config(Path(args.cwd) if args.cwd else None)


def _names(cfg: ExtConfig, choice: str) -> List[str]:
    return list(dict.fromkeys(cfg.order + list(KNOWN_BACKENDS))) if choice == ALL_BACKENDS else [choice]


def cmd_setup(cfg: ExtConfig, args: argparse.Namespace) -> int:
    for name in _names(cfg, args.backend):
        try:
            lines = get_backend(name).setup(with_sandbox(cfg, name))
        except BackendUnavailable as exc:
            lines = [str(exc)]
        print(f"[{name}]\n" + "\n".join(lines))
    return EXIT_OK


def cmd_doctor(cfg: ExtConfig, args: argparse.Namespace) -> int:
    rows, ready = [], False
    for name in _names(cfg, args.backend):
        try:
            checks = get_backend(name).doctor(with_sandbox(cfg, name))
        except BackendUnavailable as exc:
            checks = [Check("module", False, str(exc))]
        ready = ready or all(c.ok for c in checks)
        rows.append((name, checks))
    print(render.doctor_table(rows))
    return EXIT_OK if ready else EXIT_FAIL


def cmd_status(cfg: ExtConfig, args: argparse.Namespace) -> int:
    print("| backend | sẵn sàng | hết hạn mức tới | lượt gần nhất |\n|---|---|---|---|")
    for name in cfg.order:
        try:
            ok = render.mark(backend_ready(get_backend(name), cfg))
        except BackendUnavailable:
            ok = "chưa có"
        until = quota_state.exhausted_until(cfg.quota_state, name)
        last = last_run(cfg, name)
        shown = f"{last['started']} {last['status']}" if last else "-"
        print(f"| {name} | {ok} | {quota_state.iso(until) if until else '-'} | {shown} |")
    return EXIT_OK


def cmd_report(cfg: ExtConfig, args: argparse.Namespace) -> int:
    entries = ledger.read_entries(cfg.ledger)
    if args.since:
        entries = [e for e in entries if str(e.get("started", ""))[:10] >= args.since]
    for key in ("backend", "label"):
        if getattr(args, key):
            entries = [e for e in entries if e.get(key) == getattr(args, key)]
    print(render.ledger_report(entries))
    return EXIT_OK


COMMANDS = {"setup": cmd_setup, "doctor": cmd_doctor, "run": cmd_run,
            "status": cmd_status, "report": cmd_report}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](_cfg(args), args)
    except BackendUnavailable as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, ValueError) as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
