"""Read hand-ext run registry, side-session state and launcher `.meta` files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from side_session.state import load_all as load_side_states

from .claude_source import pid_alive
from .constants import (
    PROJECT_CONFIG_RELPATH, PROVIDER_CLAUDE, PS_SECTION, REPO_PLACEHOLDER, RUNS_GLOB,
    RUNS_SUBDIR, RUN_STATUS_RUNNING, SESSION_META_GLOBS_KEY, SESSION_META_SUFFIX,
    SIDE_SESSION_SECTION, SIDE_STATE_DIR_DEFAULT, SIDE_STATE_DIR_KEY, STATE_DIR_DEFAULT,
    STATE_DIR_ENV,
)
from .models import HandRun
from .timeutil import to_epoch

META_KEYS = frozenset({"uuid", "cap_usd", "started", "screen_pid", "exempt"})
TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass
class SessionMeta:
    cap_tokens: Optional[int] = None
    started_at: Optional[float] = None
    exempt: bool = False


@dataclass
class PsConfig:
    project_root: Path
    meta_globs: List[str] = field(default_factory=list)
    side_state_dir: Path = Path(".")


def state_root() -> Path:
    raw = os.environ.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT
    return Path(os.path.expanduser(raw))


def _resolve(root: Path, raw: str) -> Path:
    value = str(raw).replace(REPO_PLACEHOLDER, root.name)
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else (root / path)


def load_ps_config(root: Path) -> PsConfig:
    section: dict = {}
    side: dict = {}
    path = root / PROJECT_CONFIG_RELPATH
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: cần JSON object")
        section = data.get(PS_SECTION) or {}
        side = data.get(SIDE_SESSION_SECTION) or {}
        if not isinstance(section, dict) or not isinstance(side, dict):
            raise ValueError(f"{path}: mục {PS_SECTION}/{SIDE_SESSION_SECTION} phải là object")
    globs = section.get(SESSION_META_GLOBS_KEY) or []
    if not isinstance(globs, list) or not all(isinstance(item, str) for item in globs):
        raise ValueError(f"{path}: {PS_SECTION}.{SESSION_META_GLOBS_KEY} phải là list chuỗi")
    for pattern in globs:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"{path}: glob .meta phải tương đối trong repo: {pattern}")
    raw_dir = str(side.get(SIDE_STATE_DIR_KEY) or SIDE_STATE_DIR_DEFAULT)
    return PsConfig(project_root=root, meta_globs=list(globs),
                    side_state_dir=_resolve(root, raw_dir))


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def load_session_meta(cfg: PsConfig) -> Dict[str, SessionMeta]:
    found: Dict[str, SessionMeta] = {}
    for pattern in cfg.meta_globs:
        try:
            paths = sorted(cfg.project_root.glob(pattern))
        except (OSError, ValueError):
            continue
        for path in paths:
            if not path.is_file() or not path.name.endswith(SESSION_META_SUFFIX):
                continue
            parsed = _parse_meta(path)
            if parsed is not None and parsed[0]:
                found[parsed[0]] = parsed[1]
    return found


def _parse_meta(path: Path) -> Optional[Tuple[str, SessionMeta]]:
    values: Dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                key, separator, value = line.partition("=")
                key = key.strip()
                if separator and key in META_KEYS:
                    values[key] = value.strip()
    except OSError:
        return None
    uuid = values.get("uuid")
    if not uuid:
        return None
    cap = _number(values.get("cap_usd"))
    meta = SessionMeta(
        cap_tokens=int(cap) if cap is not None else None,
        started_at=to_epoch(values.get("started")),
        exempt=values.get("exempt", "").lower() in TRUTHY,
    )
    return uuid, meta


def _side_entry(state: Any) -> Dict[str, Any]:
    return {
        "name": str(getattr(state, "name", "") or ""),
        "provider": str(getattr(state, "provider", "") or PROVIDER_CLAUDE),
        "status": str(getattr(state, "status", "") or ""),
        "parent_session": str(getattr(state, "parent_session", "") or "") or None,
        "dir": str(getattr(state, "dir", "") or ""),
        "max_tokens": getattr(state, "max_tokens", None),
        "started": getattr(state, "started", None),
        "tokens_used": getattr(state, "tokens_used", None),
    }


def side_state_caps(cfg: PsConfig) -> Dict[str, dict]:
    try:
        states = load_side_states(cfg.side_state_dir)
    except (OSError, ValueError, TypeError, KeyError):
        return {}
    found: Dict[str, dict] = {}
    for state in states:
        uuid = str(getattr(state, "uuid", "") or "")
        if uuid and uuid not in found:
            found[uuid] = _side_entry(state)
    return found


def _tokens(raw: Any) -> Dict[str, int]:
    data = raw if isinstance(raw, dict) else {}
    tokens: Dict[str, int] = {}
    for key in ("input", "cached_input", "output"):
        try:
            tokens[key] = max(0, int(data.get(key) or 0))
        except (TypeError, ValueError):
            tokens[key] = 0
    return tokens


def _pid(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def load_hand_runs(root: Path, cutoff: float) -> List[HandRun]:
    runs: List[HandRun] = []
    folder = root / RUNS_SUBDIR
    if not folder.is_dir():
        return runs
    for path in sorted(folder.glob(RUNS_GLOB)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        status = str(data.get("status") or "")
        pid = _pid(data.get("pid"))
        started = to_epoch(data.get("started"))
        ended = to_epoch(data.get("ended"))
        running = status == RUN_STATUS_RUNNING
        if not running:
            moment = ended if ended is not None else started
            if moment is not None and moment < cutoff:
                continue
        runs.append(HandRun(
            run_id=str(data.get("run_id") or path.stem),
            label=str(data.get("label") or ""),
            backend=str(data.get("backend") or ""),
            model=str(data.get("model") or ""),
            status=status,
            parent_session=str(data["parent_session"])
            if data.get("parent_session") else None,
            tokens=_tokens(data.get("tokens")),
            started_at=started,
            ended_at=ended,
            pid=pid,
            child_pid=_pid(data.get("child_pid")),
            lost=running and pid is not None and not pid_alive(pid),
        ))
    runs.sort(key=lambda run: (-(run.started_at or 0.0), run.run_id))
    return runs
