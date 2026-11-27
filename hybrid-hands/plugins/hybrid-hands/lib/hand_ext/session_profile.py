"""Per-session profile override: one small file per Claude/Codex session, never repo config.

A session without a file keeps the configured profile (plugin → global → repo). Child
sessions opened by side-session are new sessions and therefore use the configured profile.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from shared_config import ConfigResult, load_config

from .constants import PROFILE_KEY, STATE_DIR_DEFAULT, STATE_DIR_ENV
from .native import _caller
from .profiles import ProfileError, normalize_profile

SESSION_DIR = "session-profiles"
SESSION_SOURCE = "session"
SESSION_ID_ENV = {"claude": "CLAUDE_CODE_SESSION_ID", "codex": "CODEX_THREAD_ID"}
ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,128}")
STALE_SECONDS = 30 * 24 * 3600  # file phiên quá 30 ngày coi như phiên đã chết
FILE_MODE, DIR_MODE = 0o600, 0o700


def _valid(session_id: object) -> bool:
    return isinstance(session_id, str) and bool(ID_PATTERN.fullmatch(session_id))


def session_key(env: Mapping[str, str], session_id: Optional[str] = None) -> Optional[str]:
    """`claude-<id>` / `codex-<id>`; None when the caller is ambiguous or the id is invalid."""
    if session_id is not None:
        return f"claude-{session_id}" if _valid(session_id) else None
    caller = _caller(env)
    if not caller:
        return None
    value = env.get(SESSION_ID_ENV[caller], "")
    return f"{caller}-{value}" if _valid(value) else None


def session_dir(env: Mapping[str, str] = os.environ) -> Path:
    return Path(env.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT).expanduser() / SESSION_DIR


def _path(key: str, env: Mapping[str, str]) -> Path:
    return session_dir(env) / f"{key}.json"


def read(key: str, env: Mapping[str, str] = os.environ) -> Optional[str]:
    """Canonical profile name of the session; None when absent. Raises ValueError when broken."""
    path = _path(key, env)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("file profile phiên phải là object")
    return normalize_profile(data.get(PROFILE_KEY, ""))


def _prune(directory: Path) -> None:
    cutoff = time.time() - STALE_SECONDS
    for old in directory.glob("*.json"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            continue


def write(key: str, profile: str, cwd: str, env: Mapping[str, str] = os.environ) -> Path:
    name = normalize_profile(profile)
    directory = session_dir(env)
    directory.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    _prune(directory)
    payload = {PROFILE_KEY: name, "set_at": datetime.now(timezone.utc).isoformat(), "cwd": str(cwd)}
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{key}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.chmod(tmp, FILE_MODE)
        target = _path(key, env)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def clear(key: str, env: Mapping[str, str] = os.environ) -> bool:
    path = _path(key, env)
    if not path.exists():
        return False
    path.unlink()
    return True


def apply(effective: dict, sources: dict, key: Optional[str],
          env: Mapping[str, str] = os.environ) -> bool:
    """Overlay the session profile; a broken file is ignored with one stderr warning."""
    if key is None:
        return False
    try:
        name = read(key, env)
    except (OSError, ValueError, ProfileError):
        print(f"warning: hybrid-hands: bỏ qua profile phiên hỏng ({key})", file=sys.stderr)
        return False
    if name is None:
        return False
    effective[PROFILE_KEY] = name
    sources[PROFILE_KEY] = SESSION_SOURCE
    return True


def load_with_session(cwd: Optional[Path] = None, env: Mapping[str, str] = os.environ,
                      session_id: Optional[str] = None) -> ConfigResult:
    """load_config with the session profile applied on deep copies (config objects stay intact)."""
    result = load_config(cwd)
    effective, sources = copy.deepcopy(result.effective), dict(result.sources)
    apply(effective, sources, session_key(env, session_id), env)
    return ConfigResult(result.root, effective, sources, result.paths, result.sections)
