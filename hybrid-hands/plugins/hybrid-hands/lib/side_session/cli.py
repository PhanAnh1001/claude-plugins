"""argparse entry point for side-session."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import actions
from . import constants as C
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="side-session",
                                description="Open and manage side Claude/Codex sessions in screen.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="start a side session")
    s.add_argument("--name", required=True)
    s.add_argument("--resume", action="store_true",
                   help="mở lại phiên claude đã dừng, giữ hội thoại")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    s.add_argument("--worktree", action="store_true")
    s.add_argument("--base", default=None)
    s.add_argument("--provider", choices=C.PROVIDERS, default=C.PROVIDER_CLAUDE)
    s.add_argument("--max-tokens", type=int)
    s.add_argument("--hours", type=float)
    s.add_argument("--brain", default="", help="brain session name for SendMessage")
    chrome = s.add_mutually_exclusive_group()
    chrome.add_argument("--chrome", dest="chrome", action="store_true",
                        help="mở Chrome (chỉ provider claude)")
    chrome.add_argument("--no-chrome", dest="chrome", action="store_false",
                        help="không mở Chrome")
    s.set_defaults(chrome=None)
    s.add_argument("--budget-exempt", action="store_true",
                   help="bỏ kiểm tra budget_check_cmd khi start và mã 20 khi watch")
    s.add_argument("--force-budget", action="store_true",
                   help="start dù budget_check_cmd từ chối (watch vẫn kiểm)")
    s.add_argument("--dry-run", action="store_true")
    sub.add_parser("ls", help="list sessions")
    st = sub.add_parser("stop", help="stop a session and its watchdog")
    st.add_argument("name")
    w = sub.add_parser("watch", help="token watchdog")
    w.add_argument("--name", required=True)
    w.add_argument("--interval", type=float)
    w.add_argument("--once", action="store_true")
    h = sub.add_parser("handoff", help="print the handoff summary block")
    h.add_argument("name")
    return p


HANDLERS = {"start": actions.start, "ls": actions.ls, "stop": actions.stop,
            "watch": actions.watch, "handoff": actions.handoff}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(Path.cwd())
    return HANDLERS[args.cmd](cfg, args)
