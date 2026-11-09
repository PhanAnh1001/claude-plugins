"""hand-ext command line: setup, doctor, run, status, usage, report, measure."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from shared_config import GlobalConfigError, load_config as load_shared

from . import go_live, go_usage, measure, quota_state, render, report
from .backends import BackendUnavailable, KNOWN_BACKENDS, get_backend
from .backends.base import Check
from .config import ExtConfig, load_config
from .constants import (
    ALL_BACKENDS, AUTO_BACKEND, EXIT_ALL_UNAVAILABLE, EXIT_FAIL, EXIT_OK, EXIT_USAGE, GO_LIVE_MISSING, ISOLATIONS,
    SANDBOXES,
)
from .run_cmd import auto_preflight, backend_ready, cmd_run, last_run, with_sandbox


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hand-ext",
        description="Chạy hand ngoài qua CLI đăng nhập gói subscription (không API).")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("setup", "ghi cấu hình CLI, in lệnh đăng nhập gói"),
                       ("doctor", "kiểm cài đặt, đăng nhập gói, cấu hình")):
        s = sub.add_parser(name, help=text)
        s.add_argument("--backend", default=ALL_BACKENDS)
        s.add_argument("--cwd")
    inspect = sub.add_parser("config", help="in cấu hình hiệu lực và nguồn (chỉ đọc)")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--cwd")
    pick = sub.add_parser("pick", help="chọn backend auto (chỉ đọc)")
    pick.add_argument("--json", action="store_true")
    pick.add_argument("--cwd")
    r = sub.add_parser("run", help="chạy một brief")
    r.add_argument("--brief", required=True, help="file brief hoặc - cho stdin")
    r.add_argument("--backend", default=AUTO_BACKEND)
    for flag in ("--label", "--cwd", "--model", "--effort"):
        r.add_argument(flag)
    r.add_argument("--timeout-min", type=float)
    r.add_argument("--max-tokens", type=int)
    r.add_argument("--sandbox", choices=SANDBOXES)
    r.add_argument("--isolation", choices=ISOLATIONS,
                   help="chạy trong git worktree sạch (mặc định) hoặc trực tiếp (none)")
    r.add_argument("--no-apply", action="store_true",
                   help="chỉ lưu changes.patch, không áp về thư mục gốc")
    r.add_argument("--keep-worktree", action="store_true",
                   help="giữ worktree sau khi chạy để kiểm tra")
    r.add_argument("--browser", action="store_true",
                   help="bật Playwright MCP cô lập cho backend dsh (chỉ trang công khai)")
    sub.add_parser("status", help="sẵn sàng, hạn mức, lượt gần nhất").add_argument("--cwd")
    use = sub.add_parser("usage", help="mức đã dùng gói OpenCode Go (5h/7d/30d)")
    use.add_argument("--json", action="store_true", help="in JSON của bản tóm tắt")
    use.add_argument("--cwd")
    rep = sub.add_parser("report", help="tổng lượt và token")
    for flag in ("--since", "--backend", "--label", "--cwd"):
        rep.add_argument(flag)
    mea = sub.add_parser("measure", help="đo dòng test/code/docs và thời gian chạy test")
    mea.add_argument("--runs", action="append", required=True, metavar="DIR",
                     help="thư mục runs_dir chứa các thư mục lượt; lặp lại được")
    mea.add_argument("--backend", help="chỉ lấy lượt của backend này")
    mea.add_argument("--since", help="chỉ lấy lượt bắt đầu từ ngày YYYY-MM-DD")
    return p


def _cfg(args: argparse.Namespace) -> ExtConfig:
    cwd = getattr(args, "cwd", None)
    return load_config(Path(cwd) if cwd else None)


def _names(cfg: ExtConfig, choice: str) -> List[str]:
    if choice == ALL_BACKENDS:
        return list(dict.fromkeys(cfg.order + list(cfg.backends) + list(KNOWN_BACKENDS)))
    return [choice]


def cmd_pick(cfg: ExtConfig, args: argparse.Namespace) -> int:
    result = {"backend": None, "model": None, "effort": None, "account": None, "skipped": []}
    for backend, name, reason in auto_preflight(cfg):
        if backend is None:
            result["skipped"].append({"backend": name, "reason": reason})
            continue
        options = cfg.options(name)
        account = {"codex": "gpt", "claude-main": "claude-v1", "claude": "claude-v2"}.get(name, name)
        result.update(backend=name, model=options.get("model", ""),
                      effort=options.get("effort", options.get("variant", "")), account=account)
        break
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for skipped in result["skipped"]:
            print(f"bỏ qua {skipped['backend']}: {skipped['reason']}")
        print(f"{result['backend']} model={result['model']} effort={result['effort']} account={result['account']}"
              if result["backend"] else "Không backend nào dùng được.")
    return EXIT_OK if result["backend"] else EXIT_ALL_UNAVAILABLE


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
        ready = ready or all(c.ok or not c.required for c in checks)
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
    summary = go_usage.read_summary(cfg.go_usage_summary)
    now = time.time()
    live = go_live.read_live(go_live.cache_path(go_live.claude_home(os.environ)), now)
    if live is not None:
        print()
        print(go_live.live_line(live, now))
    if summary and summary.get("models"):
        print()
        print(go_usage.format_text(summary))
    return EXIT_OK


def cmd_usage(cfg: ExtConfig, args: argparse.Namespace) -> int:
    live = go_live.refresh_and_read(cfg.go_usage_live, os.environ)
    now = time.time()
    summary = go_usage.refresh(cfg)
    if args.json:
        print(json.dumps({**summary, "live": live}, ensure_ascii=False, indent=2))
    else:
        print(go_live.live_line(live, now) if live is not None else GO_LIVE_MISSING)
        print()
        print(go_usage.format_text(summary))
    return EXIT_OK


def cmd_report(cfg: ExtConfig, args: argparse.Namespace) -> int:
    scope = report.collect(cfg)
    entries = scope.entries
    if args.since:
        entries = [e for e in entries if str(e.get("started", ""))[:10] >= args.since]
    for key in ("backend", "label"):
        if getattr(args, key):
            entries = [e for e in entries if e.get(key) == getattr(args, key)]
    print(report.format_scope(scope))
    print()
    print(render.ledger_report(entries))
    return EXIT_OK


def cmd_measure(cfg: ExtConfig, args: argparse.Namespace) -> int:
    runs = measure.collect_runs([Path(item) for item in args.runs],
                                backend=args.backend, since=args.since)
    print(measure.format_report(runs))
    return EXIT_OK


COMMANDS = {"pick": cmd_pick, "setup": cmd_setup, "doctor": cmd_doctor, "run": cmd_run,
            "status": cmd_status, "usage": cmd_usage, "report": cmd_report,
            "measure": cmd_measure}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "config":
            result = load_shared(Path(args.cwd) if args.cwd else None)
            _cfg(args)
            payload = {"effective": result.effective, "sources": result.sources, "paths": result.paths}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return EXIT_OK
        return COMMANDS[args.cmd](_cfg(args), args)
    except BackendUnavailable as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, ValueError, GlobalConfigError) as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
