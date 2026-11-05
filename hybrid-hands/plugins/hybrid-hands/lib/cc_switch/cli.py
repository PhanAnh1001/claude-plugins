"""`cc-switch` command line: term | paseo | status."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .constants import (
    SELF_EXIT_TIMEOUT_SECONDS, SELF_IDLE_SECONDS, SELF_WORKER_COMMAND,
    TERM_APP_CHOICES, TERM_APP_DEFAULT, TERM_WORKER_COMMAND,
)
from .errors import CcSwitchError
from .paseo_cmd import run_paseo
from .self_cmd import build_worker_parser, run_paseo_self, run_self_worker
from .status_cmd import run_status
from .term import run_term
from .term_self import (
    build_term_worker_parser, run_term_self, run_term_worker,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc-switch",
        description="Chuyển một phiên Claude Code giữa terminal và Paseo.")
    commands = parser.add_subparsers(dest="command", required=True)

    term = commands.add_parser(
        "term", help="chuyển phiên Paseo sang TUI claude trong terminal")
    term.add_argument("--agent", help="id agent Paseo hoặc tiền tố >= 6 ký tự")
    term.add_argument("--session", help="sessionId Claude cần chuyển")
    term.add_argument("--self", dest="self_mode", action="store_true",
                      help="tự tìm phiên Paseo đang giữ phiên hiện tại rồi mở "
                           "cửa sổ terminal (không đi với --agent/--session)")
    term.add_argument("--idle-sec", type=int, default=SELF_IDLE_SECONDS,
                      help=f"chờ transcript đứng yên bao nhiêu giây "
                           f"(mặc định {SELF_IDLE_SECONDS})")
    term.add_argument("--app", choices=TERM_APP_CHOICES,
                      default=TERM_APP_DEFAULT,
                      help=f"ứng dụng mở cửa sổ với --self "
                           f"(mặc định {TERM_APP_DEFAULT})")
    term.add_argument("--dry-run", action="store_true",
                      help="chỉ in kế hoạch hoặc lệnh claude, không chạy")

    paseo = commands.add_parser(
        "paseo", help="nạp lại (hoặc import) phiên để Paseo tiếp tục")
    paseo.add_argument("--session", help="sessionId Claude cần chuyển")
    paseo.add_argument("--self", dest="self_mode", action="store_true",
                       help="tự tìm phiên TUI hiện tại rồi chuyển nền "
                            "(không đi với --session)")
    paseo.add_argument("--idle-sec", type=int, default=SELF_IDLE_SECONDS,
                       help=f"chờ transcript đứng yên bao nhiêu giây "
                            f"(mặc định {SELF_IDLE_SECONDS})")
    paseo.add_argument("--exit-timeout", type=int,
                       default=SELF_EXIT_TIMEOUT_SECONDS,
                       help=f"chờ TUI thoát sau SIGTERM bao nhiêu giây "
                            f"(mặc định {SELF_EXIT_TIMEOUT_SECONDS})")
    paseo.add_argument("--dry-run", action="store_true",
                       help="chỉ in kế hoạch hoặc lệnh paseo, không chạy")

    status = commands.add_parser("status", help="bảng agent và nơi đang giữ phiên")
    status.add_argument("--all", action="store_true",
                        help="mọi project thay vì chỉ project hiện tại")
    return parser


def _split_extra(argv: List[str]) -> tuple:
    """Everything after `--` belongs to `claude`, not to cc-switch."""
    if argv and argv[0] == "term" and "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1:]
    return argv, []


def _report(exc: CcSwitchError) -> int:
    stream = sys.stdout if exc.to_stdout else sys.stderr
    print(exc.message, file=stream)
    return exc.code


def main(argv: Optional[List[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == [SELF_WORKER_COMMAND]:
        opts = build_worker_parser().parse_args(raw[1:])
        try:
            return run_self_worker(opts)
        except CcSwitchError as exc:
            return _report(exc)
    if raw[:1] == [TERM_WORKER_COMMAND]:
        opts = build_term_worker_parser().parse_args(raw[1:])
        try:
            return run_term_worker(opts)
        except CcSwitchError as exc:
            return _report(exc)

    raw, extra = _split_extra(raw)
    parser = build_parser()
    opts = parser.parse_args(raw)
    opts.extra = extra
    try:
        if opts.command == "term":
            if opts.self_mode:
                return run_term_self(opts)
            return run_term(opts)
        if opts.command == "paseo":
            if opts.self_mode:
                return run_paseo_self(opts)
            return run_paseo(opts)
        return run_status(opts)
    except CcSwitchError as exc:
        return _report(exc)
