"""CODEX_HOME helpers for the codex backend: config.toml top-level keys and login mode.

Python 3.9 has no tomllib, so config.toml is edited textually: keys before the first
table header are set or removed, every other line and table is kept.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, Optional

CONFIG_FILE = "config.toml"
AUTH_FILE = "auth.json"
SUBSCRIPTION_AUTH_MODE = "chatgpt"
API_KEY_AUTH_MODE = "apikey"
API_KEY_FIELD = "OPENAI_API_KEY"
# service_tier is an API pricing tier left by the old API-key setup; subscription runs drop it.
REMOVED_KEYS = ("service_tier",)
TABLE_HEADER_RE = re.compile(r"^\s*\[")
KEY_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"?([^"\n]*)"?\s*$')


def _key_line(key: str, value: str) -> str:
    return f'{key} = "{value}"\n'


def merge_top_level(text: str, keys: Dict[str, str], removed: Iterable[str] = REMOVED_KEYS) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    first_table = next((i for i, l in enumerate(lines) if TABLE_HEADER_RE.match(l)), len(lines))
    top, rest = lines[:first_table], lines[first_table:]
    drop = set(removed)
    missing = dict(keys)
    kept = []
    for line in top:
        match = KEY_RE.match(line)
        name = match.group(1) if match else None
        if name in drop:
            continue
        kept.append(_key_line(name, missing.pop(name)) if name in missing else line)
    insert_at = len(kept)
    while insert_at and not kept[insert_at - 1].strip():
        insert_at -= 1
    kept = kept[:insert_at] + [_key_line(k, v) for k, v in missing.items()] + kept[insert_at:]
    if rest and kept and kept[-1].strip():
        kept.append("\n")
    return "".join(kept + rest)


def top_level_values(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if TABLE_HEADER_RE.match(line):
            break
        match = KEY_RE.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def write_config(home: Path, keys: Dict[str, str]) -> bool:
    """Return True when config.toml changed."""
    home.mkdir(parents=True, exist_ok=True)
    path = home / CONFIG_FILE
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    new = merge_top_level(old, keys)
    if new == old:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def auth_mode(home: Path) -> Optional[str]:
    """Login mode only ('chatgpt', 'apikey', ...); reads one field, never returns secrets."""
    path = home / AUTH_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "unreadable"
    mode = data.get("auth_mode") if isinstance(data, dict) else None
    if isinstance(mode, str):
        return mode.lower()
    key = data.get(API_KEY_FIELD) if isinstance(data, dict) else None
    return API_KEY_AUTH_MODE if isinstance(key, str) and key else "unknown"
