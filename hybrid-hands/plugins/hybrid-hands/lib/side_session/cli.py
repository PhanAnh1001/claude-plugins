"""argparse entry point for side-session."""
from __future__ import annotations

import argparse
import sys

from shared_config import GlobalConfigError
from pathlib import Path

from . import gc
from . import actions
from . import attach
from . import constants as C
from . import state
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
    s.add_argument("--main", action="store_true",
                   help="mở phiên chính: mặc định Codex Sol high trên Paseo; "
                        "--provider claude mở Claude Opus high trên Paseo")
    s.add_argument("--worktree", action="store_true")
    s.add_argument("--new-workspace", action="store_true",
                   help="tạo workspace Paseo riêng thay vì dùng lại workspace của phiên đang chat")
    s.add_argument("--no-sparse", action="store_true",
                   help="bỏ qua side_session.worktree_sparse_exclude, checkout đủ")
    s.add_argument("--ignore-disk-guard", action="store_true",
                   help="chủ động vượt chặn dung lượng ổ khi tạo worktree")
    s.add_argument("--base", default=None)
    s.add_argument("--provider", choices=C.PROVIDERS, default=None,
                   help="codex (mặc định cho start), claude (mặc định cho --resume) hoặc dsh")
    s.add_argument("--account", default=None, help="tài khoản Claude v1/v2/v… (mặc định v1; resume giữ state)")
    s.add_argument("--model", default=None,
                   help="model cho Codex/Claude, hoặc chuyển --model cho hand-ext")
    s.add_argument("--effort", default=None,
                   help="effort cho Codex/Claude, hoặc chuyển --effort cho hand-ext")
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
    send = sub.add_parser("send", help="continue the exact Paseo side agent")
    send.add_argument("--name", required=True)
    send.add_argument("--prompt-file", required=True)
    send.add_argument("--force-budget", action="store_true")
    tidy = sub.add_parser("tidy", help="inspect plugin workspaces; --apply archives eligible IDs")
    tidy.add_argument("--name")
    tidy.add_argument("--names", action="store_true", help="inspect/rename titles only")
    tidy.add_argument("--apply", action="store_true")
    collector = sub.add_parser("gc", help="inspect worktrees; --apply removes eligible worktrees")
    collector.add_argument("--name")
    collector.add_argument("--apply", action="store_true")
    collector.add_argument("--include-unmerged", action="store_true")
    collector.add_argument("--prune-branches", action="store_true")
    collector.add_argument("--json", action="store_true")
    collector.add_argument("--fetch", action="store_true", help="explicitly fetch origin before inspection")
    sub.add_parser("ls", help="list sessions")
    st = sub.add_parser("stop", help="stop a session and its watchdog")
    st.add_argument("name")
    w = sub.add_parser("watch", help="token watchdog")
    w.add_argument("--name", required=True)
    w.add_argument("--interval", type=float)
    w.add_argument("--once", action="store_true")
    h = sub.add_parser("handoff", help="print the handoff summary block")
    h.add_argument("name")
    at = sub.add_parser("attach", help="gắn vào screen của phiên phụ đang chạy")
    at.add_argument("name", nargs="?", default=None,
                    help="tên phiên phụ (bỏ trống để chọn trong menu)")
    return p


HANDLERS = {"gc": gc.run, "tidy": actions.tidy,"send": actions.send,"start": actions.start, "ls": actions.ls, "stop": actions.stop,
            "watch": actions.watch, "handoff": actions.handoff}


def _attach_transport_lookup():
    """Optional state lookup for `attach NAME`; Paseo terminals may run outside a repo."""
    try:
        cfg = load_config(Path.cwd())
    except (SystemExit, OSError, ValueError):
        return None

    def lookup(name: str):
        path = state.state_path(cfg.state_dir, name)
        if not path.is_file():
            return None
        try:
            st = state.load(cfg.state_dir, name)
        except (OSError, ValueError):
            return None
        return (st.transport, st.paseo_agent_id)

    return lookup


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "attach":
            # Paseo runs terminal profiles from an arbitrary cwd with no project config.
            return attach.main(args.name, transport_fn=_attach_transport_lookup())
        cfg = load_config(Path.cwd())
        return HANDLERS[args.cmd](cfg, args)
    except GlobalConfigError as exc:
        print(f"side-session: {exc}", file=sys.stderr)
        return 1
