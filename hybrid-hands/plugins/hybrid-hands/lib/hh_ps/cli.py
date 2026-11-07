"""`hh-ps`: tree of Claude Code sessions, subagents and external hand runs."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

from .constants import ENDED_FLAG, FULL_FLAG, MIN_WATCH_SECONDS
from .render import color_enabled, render_json, render_text
from .timeutil import parse_since
from .tree import build_snapshot

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _uuid(raw: str) -> str:
    if not UUID_RE.match(raw):
        raise argparse.ArgumentTypeError("--main-session cần một UUID hợp lệ")
    return raw


def _watch_seconds(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("--watch cần số giây")
    if value < MIN_WATCH_SECONDS:
        raise argparse.ArgumentTypeError(f"--watch tối thiểu {MIN_WATCH_SECONDS} giây")
    return value


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("--count cần số nguyên dương")
    if value < 1:
        raise argparse.ArgumentTypeError("--count phải lớn hơn 0")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hh-ps",
        description="Cây phiên Claude Code → subagent → lượt hand ngoài (chỉ đọc).")
    parser.add_argument("--since", default="6h",
                        help="khoảng thời gian cho phiên/subagent/lượt đã xong (m/h/d)")
    parser.add_argument("--all", action="store_true", help="mọi project")
    parser.add_argument(ENDED_FLAG, action="store_true",
                        help="tương thích: mặc định đã hiện cây phiên đã kết thúc")
    parser.add_argument(FULL_FLAG, action="store_true",
                        help="tương thích: mặc định đã liệt kê đủ mọi việc con")
    parser.add_argument("--once", action="store_true", help="chạy một lần (mặc định)")
    parser.add_argument("--json", action="store_true", help="in JSON")
    parser.add_argument("--watch", type=_watch_seconds,
                        help=f"vẽ lại mỗi N giây (tối thiểu {MIN_WATCH_SECONDS})")
    parser.add_argument("--count", type=_positive_int,
                        help="dừng sau K lần vẽ (dùng với --watch)")
    parser.add_argument("--cwd", help="thư mục dự án để lọc (mặc định cwd)")
    parser.add_argument("--main-session", type=_uuid,
                        help="UUID phiên chính, đè CLAUDE_CODE_SESSION_ID")
    return parser


def _emit(snapshot, as_json: bool, color: bool, full: bool) -> None:
    if as_json:
        print(json.dumps(render_json(snapshot), ensure_ascii=False, indent=2))
    else:
        print(render_text(snapshot, color=color, full=full))


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.count is not None and args.watch is None:
        parser.error("--count chỉ dùng với --watch")
    try:
        since = parse_since(args.since)
    except ValueError as exc:
        parser.error(str(exc))
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    drawn = 0
    try:
        while True:
            snapshot = build_snapshot(cwd, since, args.all,
                                      main_session_id=args.main_session)
            color = color_enabled(sys.stdout)
            if args.watch is not None and drawn and sys.stdout.isatty():
                print("\033[2J\033[H", end="")
            _emit(snapshot, args.json, color, args.full)
            drawn += 1
            if args.once or args.watch is None or (args.count is not None and drawn >= args.count):
                return 0
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        print(f"hh-ps: {exc}", file=sys.stderr)
        return 2
