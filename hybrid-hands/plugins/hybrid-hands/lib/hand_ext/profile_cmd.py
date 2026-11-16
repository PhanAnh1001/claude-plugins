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
from .profiles import ProfileError, active_profile, profile_table, role_spec

PICK_ROLES = ("code", "collect", "chrome")
TIER_CHOICES = (1, 2)
CLAUDE_FAMILIES = ("opus", "sonnet", "haiku", "fable")
GUARDED_BACKEND = "claude-v1"  # chỉ v1 có guard ngày (giữ ≥8%/ngày)


def register(sub) -> None:
    parser = sub.add_parser("profile", help="xem/đặt profile vai của repo")
    actions = parser.add_subparsers(dest="profile_action")
    setter = actions.add_parser("set")
    setter.add_argument("name", choices=PROFILE_NAMES)
    for item in (parser, setter):
        item.add_argument("--cwd", default=argparse.SUPPRESS)
        item.add_argument("--json", action="store_true", default=argparse.SUPPRESS)


def add_pick_flags(pick) -> None:
    pick.add_argument("--role", choices=PICK_ROLES)
    pick.add_argument("--tier", type=int, choices=TIER_CHOICES)


def _cwd(args) -> Optional[Path]:
    cwd = getattr(args, "cwd", None)
    return Path(cwd) if cwd else None


def _show(args) -> int:
    result = load_shared(_cwd(args))
    try:
        profile = active_profile(result.effective)
        table = profile_table(result.effective)
    except ProfileError as exc:
        print(f"profile: {exc}", file=sys.stderr)
        return EXIT_USAGE
    source = result.sources.get(PROFILE_KEY, "plugin")
    payload = {"profile": profile, "source": source,
               "file": result.paths.get(source, {}).get("path", "plugin"), "roles": table}
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"profile: {profile} [{source}]")
    for label, spec in table.items():
        print(f"  {label:<10} {spec['provider']}@{spec['account']} {spec['model']} {spec['effort']}")
    return EXIT_OK


def _set(args) -> int:
    from .models_cmd import _write
    result = load_shared(_cwd(args))
    path = Path(result.paths["repo"]["path"])
    stamps = {Path(info["path"]): file_stamp(Path(info["path"])) for info in result.paths.values()}
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(raw, dict):
        raise ValueError("file cấu hình repo phải là object")
    if raw.get(PROFILE_KEY) != args.name:
        raw[PROFILE_KEY] = args.name
        _write(path, raw, stamps)
    print(f"profile = {args.name} → {path}")
    return EXIT_OK


def command(args) -> int:
    return _set(args) if getattr(args, "profile_action", None) == "set" else _show(args)


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
    effective = load_shared(_cwd(args) or cfg.root).effective
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
