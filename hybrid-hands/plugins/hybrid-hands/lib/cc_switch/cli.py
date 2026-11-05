"""`cc-switch` command line: term | paseo | status."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .errors import CcSwitchError
from .paseo_cmd import run_paseo
from .status_cmd import run_status
from .term import run_term


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc-switch",
        description="Chuyển một phiên Claude Code giữa terminal và Paseo.")
    commands = parser.add_subparsers(dest="command", required=True)

    term = commands.add_parser(
        "term", help="chuyển phiên Paseo sang TUI claude trong terminal")
    term.add_argument("--agent", help="id agent Paseo hoặc tiền tố >= 6 ký tự")
    term.add_argument("--session", help="sessionId Claude cần chuyển")
    term.add_argument("--dry-run", action="store_true",
                      help="chỉ in lệnh claude, không chạy")

    paseo = commands.add_parser(
        "paseo", help="nạp lại (hoặc import) phiên để Paseo tiếp tục")
    paseo.add_argument("--session", help="sessionId Claude cần chuyển")
    paseo.add_argument("--dry-run", action="store_true",
                       help="chỉ in lệnh paseo, không chạy")

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


def main(argv: Optional[List[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    raw, extra = _split_extra(raw)
    parser = build_parser()
    opts = parser.parse_args(raw)
    opts.extra = extra
    try:
        if opts.command == "term":
            return run_term(opts)
        if opts.command == "paseo":
            return run_paseo(opts)
        return run_status(opts)
    except CcSwitchError as exc:
        stream = sys.stdout if exc.to_stdout else sys.stderr
        print(exc.message, file=stream)
        return exc.code
