"""`hand-ext profile [set NAME]` and `hand-ext pick --role`: profile layer on the CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from shared_config import file_stamp, load_config as load_shared

from .constants import (EXIT_ALL_UNAVAILABLE, EXIT_OK, EXIT_USAGE, PROFILE_KEY,
                        PROFILE_NAMES)
from .profiles import ProfileError, active_profile, normalize_profile, profile_table, role_spec
from . import session_profile

PICK_ROLES = ("code", "collect", "chrome")
TIER_CHOICES = (1, 2)
CLAUDE_FAMILIES = ("opus", "sonnet", "haiku", "fable")
ACCOUNTS = ("v1", "v2")  # chỉ hợp lệ sau claude-mono
GUARDED_BACKEND = "claude-v1"  # chỉ v1 có guard ngày (giữ ≥8%/ngày)


def register(sub) -> None:
    parser = sub.add_parser("profile", help="xem/đặt profile vai của repo")
    actions = parser.add_subparsers(dest="profile_action")
    setter = actions.add_parser("set")
    setter.add_argument("name", help=", ".join(PROFILE_NAMES))
    setter.add_argument("account", nargs="?", choices=ACCOUNTS)
    session = actions.add_parser("session", help="profile riêng cho phiên hiện tại (không ghi cấu hình repo)")
    session.add_argument("name", nargs="?")
    session.add_argument("account", nargs="?", choices=ACCOUNTS)
    session.add_argument("--clear", action="store_true")
    for item in (parser, setter, session):
        item.add_argument("--cwd", default=argparse.SUPPRESS)
        item.add_argument("--json", action="store_true", default=argparse.SUPPRESS)


def add_pick_flags(pick) -> None:
    pick.add_argument("--role", choices=PICK_ROLES)
    pick.add_argument("--tier", type=int, choices=TIER_CHOICES)


def _cwd(args) -> Optional[Path]:
    cwd = getattr(args, "cwd", None)
    return Path(cwd) if cwd else None


def _config_profile(result) -> tuple[str, str]:
    """(configured profile or "chưa đặt", its source) ignoring any session override."""
    name = result.effective.get(PROFILE_KEY)
    try:
        name = active_profile(result.effective)
    except ProfileError:
        name = "chưa đặt" if name is None else str(name)
    return name, result.sources.get(PROFILE_KEY, "plugin")


def _show(args) -> int:
    key = session_profile.session_key(os.environ)
    base = load_shared(_cwd(args))
    result = session_profile.load_with_session(_cwd(args), os.environ)
    try:
        profile = active_profile(result.effective)
        table = profile_table(result.effective)
    except ProfileError as exc:
        print(f"profile: {exc}", file=sys.stderr)
        return EXIT_USAGE
    source = result.sources.get(PROFILE_KEY, "plugin")
    config_profile, config_source = _config_profile(base)
    file = (str(session_profile.session_dir() / f"{key}.json")
            if source == session_profile.SESSION_SOURCE
            else result.paths.get(source, {}).get("path", "plugin"))
    payload = {"profile": profile, "source": source, "file": file, "roles": table,
               "session_key": key, "config_profile": config_profile}
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"profile: {profile} [{source}]")
    if config_profile != profile:
        print(f"config: {config_profile} [{config_source}]")
    for label, spec in table.items():
        print(f"  {label:<10} {spec['provider']}@{spec['account']} {spec['model']} {spec['effort']}")
    return EXIT_OK


def _set(args) -> int:
    from .models_cmd import _write
    try:
        name = normalize_profile(args.name, args.account)
    except ProfileError as exc:
        print(f"profile set: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE) from None  # như argparse từ chối tên lạ
    result = load_shared(_cwd(args))
    path = Path(result.paths["repo"]["path"])
    stamps = {Path(info["path"]): file_stamp(Path(info["path"])) for info in result.paths.values()}
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(raw, dict):
        raise ValueError("file cấu hình repo phải là object")
    if raw.get(PROFILE_KEY) != name:
        raw[PROFILE_KEY] = name
        _write(path, raw, stamps)
    print(f"profile = {name} → {path}")
    return EXIT_OK


def _session(args) -> int:
    key = session_profile.session_key(os.environ)
    if key is None:
        print("profile session: không xác định được phiên (cần đúng một trong CLAUDECODE=1 + "
              "CLAUDE_CODE_SESSION_ID hoặc CODEX_THREAD_ID hợp lệ); không ghi gì.", file=sys.stderr)
        return EXIT_USAGE
    if args.clear:
        session_profile.clear(key)
        name, source = _config_profile(load_shared(_cwd(args)))
        print(f"đã xoá profile phiên ({key}); dùng profile cấu hình: {name} [{source}]")
        return EXIT_OK
    if args.name is None:
        try:
            current = session_profile.read(key)
        except (OSError, ValueError, ProfileError):
            current = "hỏng (bỏ qua)"
        name, source = _config_profile(load_shared(_cwd(args)))
        print(f"phiên: {key}\nprofile phiên: {current or 'không có'}\nprofile cấu hình: {name} [{source}]")
        return EXIT_OK
    try:
        name = normalize_profile(args.name, args.account)
    except ProfileError as exc:
        print(f"profile session: {exc}", file=sys.stderr)
        return EXIT_USAGE
    session_profile.write(key, name, str(_cwd(args) or Path.cwd()))
    print(f"profile phiên = {name} ({key})")
    return _show(args)


def command(args) -> int:
    action = getattr(args, "profile_action", None)
    if action == "set":
        return _set(args)
    return _session(args) if action == "session" else _show(args)


def backend_name(spec: dict) -> str:
    return f"claude-{spec['account']}" if spec["provider"] == "claude" else spec["provider"]


def agent_model(spec: dict) -> str:
    if spec["provider"] != "claude":
        return ""
    return next((family for family in CLAUDE_FAMILIES if family in spec["model"]), "")


def _day_guard(cfg, backend: str) -> Optional[str]:
    if backend != GUARDED_BACKEND:
        return None
    from .backends import get_backend
    from .run_cmd import day_guard
    return day_guard(get_backend(backend), cfg)


def pick_role(cfg, args) -> int:
    from .native import role_native
    effective = session_profile.load_with_session(_cwd(args) or cfg.root, os.environ).effective
    try:
        spec = role_spec(effective, args.role, args.tier)
    except ProfileError as exc:
        print(f"pick: {exc}", file=sys.stderr)
        return EXIT_USAGE
    backend = backend_name(spec)
    result = {**spec, "backend": backend, "agent_model": agent_model(spec)}
    blocked = _day_guard(cfg, backend)
    native, reason = (False, blocked) if blocked else role_native(effective, spec, os.environ)
    result.update(native=native, native_reason=reason, guard_blocked=bool(blocked))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['role']} → {backend} model={spec['model']} effort={spec['effort']} "
              f"native={native} ({reason})")
    return EXIT_ALL_UNAVAILABLE if blocked else EXIT_OK
