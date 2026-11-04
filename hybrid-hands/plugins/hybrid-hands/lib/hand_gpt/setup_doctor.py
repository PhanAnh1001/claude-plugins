"""`setup` (idempotent top-level keys in $CODEX_HOME/config.toml) and `doctor` checks.

Python 3.9 has no tomllib, so the file is edited textually: keys before the first
table header are set, other keys and tables are kept, the legacy [profiles.hand] is dropped.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .codex_runner import codex_bin
from .config import HandConfig
from .constants import (
    AUTH_FILE, CONFIG_FILE, LEGACY_PROFILE_HEADER, LOGIN_COMMAND, MIN_CODEX_VERSION,
)
from . import ledger

API_KEY_AUTH_MODE = "apikey"
API_KEY_FIELD = "OPENAI_API_KEY"
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
TABLE_HEADER_RE = re.compile(r"^\s*\[")
KEY_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"?([^"\n]*)"?\s*$')


def desired_keys(cfg: HandConfig) -> Dict[str, str]:
    """Top-level keys: this CODEX_HOME is hand-only, so every codex using it defaults to them."""
    return {
        "model": cfg.model,
        "service_tier": cfg.service_tier,
        "model_reasoning_effort": cfg.effort,
        "sandbox_mode": cfg.sandbox,
    }


def _key_line(key: str, value: str) -> str:
    return f'{key} = "{value}"\n'


def _drop_table(lines: List[str], header: str) -> List[str]:
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        return lines
    end = next((i for i in range(start + 1, len(lines)) if TABLE_HEADER_RE.match(lines[i])),
               len(lines))
    head = lines[:start]
    while head and not head[-1].strip():
        head.pop()
    tail = lines[end:]
    return head + (["\n"] if head and tail else []) + tail


def merge_top_level(text: str, keys: Dict[str, str]) -> str:
    """Set keys before the first table header, keep everything else, drop the legacy table."""
    lines = _drop_table(text.splitlines(keepends=True), LEGACY_PROFILE_HEADER)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    first_table = next((i for i, l in enumerate(lines) if TABLE_HEADER_RE.match(l)), len(lines))
    top, rest = lines[:first_table], lines[first_table:]
    missing = dict(keys)
    for i, line in enumerate(top):
        match = KEY_RE.match(line)
        if match and match.group(1) in missing:
            top[i] = _key_line(match.group(1), missing.pop(match.group(1)))
    insert_at = len(top)
    while insert_at and not top[insert_at - 1].strip():
        insert_at -= 1
    added = [_key_line(k, v) for k, v in missing.items()]
    top = top[:insert_at] + added + top[insert_at:]
    if rest and top and top[-1].strip():
        top.append("\n")
    return "".join(top + rest)


def run_setup(cfg: HandConfig) -> Tuple[bool, Path]:
    """Return (changed, config_path)."""
    cfg.codex_home.mkdir(parents=True, exist_ok=True)
    path = cfg.codex_home / CONFIG_FILE
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    new = merge_top_level(old, desired_keys(cfg))
    if new == old:
        return False, path
    path.write_text(new, encoding="utf-8")
    return True, path


def top_level_values(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if TABLE_HEADER_RE.match(line):
            break
        match = KEY_RE.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def login_hint(cfg: HandConfig) -> str:
    return LOGIN_COMMAND.format(home=cfg.codex_home)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def parse_version(text: str) -> Optional[Tuple[int, int, int]]:
    match = VERSION_RE.search(text)
    return tuple(int(g) for g in match.groups()) if match else None  # type: ignore[return-value]


def _check_codex() -> Check:
    try:
        out = subprocess.run([codex_bin(), "--version"], capture_output=True, text=True,
                             timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check("codex", False, f"không chạy được: {exc.__class__.__name__}")
    version = parse_version(out.stdout + out.stderr)
    need = ".".join(map(str, MIN_CODEX_VERSION))
    if version is None:
        return Check("codex", False, "không đọc được version")
    shown = ".".join(map(str, version))
    if version < MIN_CODEX_VERSION:
        return Check("codex", False, f"{shown} < {need} (service_tier flex chưa có hiệu lực)")
    return Check("codex", True, shown)


def _check_config(cfg: HandConfig) -> Check:
    path = cfg.codex_home / CONFIG_FILE
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    current = top_level_values(text)
    wrong = [k for k, v in desired_keys(cfg).items() if current.get(k) != v]
    ok = not wrong and LEGACY_PROFILE_HEADER not in text
    detail = str(path) if ok else f"{path} lệch {wrong or 'khối cũ'}; chạy `hand-gpt setup`"
    return Check("config", ok, detail)


def auth_mode(codex_home: Path) -> Optional[str]:
    """Login mode only ('apikey', 'chatgpt', ...). Never returns secret values."""
    path = codex_home / AUTH_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "unreadable"
    mode = data.get("auth_mode")
    if isinstance(mode, str):
        return mode.lower()
    key = data.get(API_KEY_FIELD)
    return API_KEY_AUTH_MODE if isinstance(key, str) and key else "unknown"


def _check_auth(cfg: HandConfig) -> Check:
    mode = auth_mode(cfg.codex_home)
    if mode is None:
        return Check("login", False, f"chưa đăng nhập; chạy trong terminal riêng: {login_hint(cfg)}")
    ok = mode == API_KEY_AUTH_MODE
    return Check("login", ok, f"chế độ {mode}" + ("" if ok else f"; cần API key: {login_hint(cfg)}"))


def _check_ledger(cfg: HandConfig) -> Check:
    ok = ledger.check_writable(cfg.ledger)
    return Check("ledger", ok, str(cfg.ledger))


def run_doctor(cfg: HandConfig) -> List[Check]:
    return [_check_codex(), _check_config(cfg), _check_auth(cfg), _check_ledger(cfg)]
