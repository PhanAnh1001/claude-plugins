"""Paths, project root discovery and safe JSON reads."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterator, Optional

from hh_ps.claude_source import claude_config_dir
from hh_ps.constants import STATE_DIR_DEFAULT, STATE_DIR_ENV

from .constants import (
    AGENT_FILE_SUFFIX, AGENTS_SUBDIR, GIT_TIMEOUT_SECONDS, PASEO_HOME_DEFAULT,
    PASEO_HOME_ENV, SHORT_ID_CHARS,
)


def state_dir() -> Path:
    """Machine-wide state root, overridable for tests like the handoff ledger."""
    raw = os.environ.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT
    return Path(os.path.expanduser(raw))


def paseo_home() -> Path:
    raw = os.environ.get(PASEO_HOME_ENV) or PASEO_HOME_DEFAULT
    return Path(os.path.expanduser(raw))


def claude_dir() -> Path:
    return claude_config_dir()


def resolve_project(start: Optional[Path] = None) -> Path:
    """Git toplevel of `start`, else its real path (no shell, bounded)."""
    cwd = Path(start) if start is not None else Path.cwd()
    result = None
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0:
        top = result.stdout.strip()
        if top:
            try:
                return Path(top).resolve()
            except (OSError, RuntimeError):
                pass
    try:
        return cwd.resolve()
    except (OSError, RuntimeError):
        return cwd


def read_json(path: Path) -> Optional[dict]:
    """Read one JSON object; never opens *.key files (callers pass .json only)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def same_path(left: str, right: Path) -> bool:
    if not left:
        return False
    try:
        return Path(left).resolve() == right.resolve()
    except (OSError, RuntimeError):
        return False


def agent_files() -> Iterator[Path]:
    folder = paseo_home() / AGENTS_SUBDIR
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob(f"*{AGENT_FILE_SUFFIX}")):
        if path.is_file():
            yield path


def short_id(value: str, length: int = SHORT_ID_CHARS) -> str:
    return value[:length] if value else "-"


def display(value: str, width: int) -> str:
    return value if len(value) <= width else value[:width - 1] + "…"
