"""Read live Claude Code sessions and join them with transcripts and subagents."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .constants import (
    CLAUDE_CONFIG_DEFAULT, CLAUDE_CONFIG_ENV, LIVE_STATUSES, PROJECTS_SUBDIR,
    SESSIONS_SUBDIR, STATUS_ENDED, STATUS_IDLE, SUBAGENTS_SUBDIR, TRANSCRIPT_SUFFIX,
)
from .models import Session
from .transcript_source import TranscriptInfo, load_subagents, parse_transcript
from .timeutil import to_epoch

SESSION_ID_CHARS = 8


def claude_config_dir() -> Path:
    raw = os.environ.get(CLAUDE_CONFIG_ENV) or CLAUDE_CONFIG_DEFAULT
    return Path(os.path.expanduser(raw))


def pid_alive(pid: Any) -> bool:
    try:
        number = int(pid)
    except (ValueError, TypeError):
        return False
    if number <= 0:
        return False
    try:
        os.kill(number, 0)
    except (ProcessLookupError, OverflowError, ValueError):
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def slugify(path: Path) -> str:
    """Claude project slug: absolute cwd with '/' and '.' replaced by '-'."""
    return str(path).replace("/", "-").replace(".", "-")


def short_session_id(session_id: str) -> str:
    return session_id[:SESSION_ID_CHARS]


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _ms(value: Any) -> Optional[float]:
    return to_epoch(value)


def _live_sessions(config_dir: Path) -> Dict[str, dict]:
    found: Dict[str, dict] = {}
    folder = config_dir / SESSIONS_SUBDIR
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        data = _read_json(path)
        if not data or not data.get("sessionId"):
            continue
        session_id = str(data["sessionId"])
        data["_alive"] = pid_alive(data.get("pid"))
        data["_updated"] = _ms(data.get("updatedAt")) or 0.0
        previous = found.get(session_id)
        if previous is None or (data["_alive"], data["_updated"]) > (
                previous["_alive"], previous["_updated"]):
            found[session_id] = data
    return found


def _transcript_paths(config_dir: Path) -> Dict[str, Path]:
    """sessionId -> newest transcript, searched across every project slug."""
    found: Dict[str, tuple] = {}
    folder = config_dir / PROJECTS_SUBDIR
    if not folder.is_dir():
        return {}
    for path in folder.glob(f"*/*{TRANSCRIPT_SUFFIX}"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        current = found.get(path.stem)
        if current is None or mtime > current[1]:
            found[path.stem] = (path, mtime)
    return {key: value[0] for key, value in found.items()}


def _in_project(cwd: str, slug: str, root: Path) -> bool:
    if cwd:
        try:
            path = Path(cwd).resolve()
            root = root.resolve()
        except (OSError, RuntimeError):
            return False
        return path == root or root in path.parents
    root_slug = slugify(root)
    return slug == root_slug or slug.startswith(root_slug + "-")


def _subagent_dirs(config_dir: Path) -> Dict[str, List[Path]]:
    found: Dict[str, List[Path]] = {}
    folder = config_dir / PROJECTS_SUBDIR
    if not folder.is_dir():
        return found
    for path in folder.glob(f"*/*/{SUBAGENTS_SUBDIR}"):
        if path.is_dir():
            found.setdefault(path.parent.name, []).append(path)
    return found


def _new_session(session_id: str, data: dict, main_session_id: Optional[str]) -> Session:
    status = str(data.get("status") or STATUS_IDLE)
    return Session(
        session_id=session_id,
        name=str(data.get("name") or short_session_id(session_id)),
        status=status if status in LIVE_STATUSES else STATUS_IDLE,
        cwd=str(data.get("cwd") or ""),
        context_tokens=None,
        started_at=_ms(data.get("startedAt")),
        last_activity=_ms(data.get("updatedAt")),
        is_main=session_id == main_session_id,
        live=True,
    )


def _ended_session(session_id: str, info: TranscriptInfo, old: dict, project_root: Path,
                   main_session_id: Optional[str]) -> Session:
    return Session(
        session_id=session_id,
        name=info.custom_title or str(old.get("name") or "") or
        short_session_id(session_id),
        status=STATUS_ENDED,
        cwd=info.cwd or str(old.get("cwd") or "") or (
            str(project_root) if info.slug == slugify(project_root) else ""),
        context_tokens=info.context_tokens,
        started_at=_ms(old.get("startedAt")) or info.started_at,
        last_activity=info.last_activity or info.mtime,
        is_main=session_id == main_session_id,
        live=False,
    )


def _merge(session: Session, info: TranscriptInfo, path: Path) -> None:
    if info.custom_title:
        session.name = info.custom_title
    if not session.cwd:
        session.cwd = info.cwd
    if info.context_tokens is not None:
        session.context_tokens = info.context_tokens
    if session.started_at is None:
        session.started_at = info.started_at
    if info.last_activity is not None:
        session.last_activity = max(session.last_activity or 0.0, info.last_activity)
    session.transcript_path = path
    session.project_slug = info.slug


def load_sessions(config_dir: Path, cutoff: float, project_root: Path,
                  all_projects: bool, main_session_id: Optional[str],
                  now: float,
                  include_ids: Optional[Set[str]] = None) -> List[Session]:
    records = _live_sessions(config_dir)
    live = {sid: data for sid, data in records.items() if data.get("_alive")}
    dead = {sid: data for sid, data in records.items() if not data.get("_alive")}
    sessions: Dict[str, Session] = {
        sid: _new_session(sid, data, main_session_id) for sid, data in live.items()}
    for session_id, path in _transcript_paths(config_dir).items():
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if session_id not in live and mtime < cutoff:
            continue
        info = parse_transcript(path)
        session = sessions.get(session_id)
        if session is None:
            old = dead.get(session_id, {})
            pulled = False
            if not all_projects:
                inside = _in_project(info.cwd or str(old.get("cwd") or ""),
                                     info.slug, project_root)
                if not inside and (include_ids is None or session_id not in include_ids):
                    continue
                pulled = not inside
            session = _ended_session(session_id, info, old, project_root, main_session_id)
            session.pulled_in = pulled
            sessions[session_id] = session
        else:
            _merge(session, info, path)
        session.transcript_path = path
        session.project_slug = info.slug
    subagent_index = _subagent_dirs(config_dir)
    for session in sessions.values():
        session.subagents = load_subagents(subagent_index.get(session.session_id, []),
                                           cutoff, now)
    return sorted(sessions.values(), key=_session_sort_key)


def _session_sort_key(session: Session):
    return (not session.live, not session.is_main,
            -(session.last_activity or 0.0), session.session_id)
