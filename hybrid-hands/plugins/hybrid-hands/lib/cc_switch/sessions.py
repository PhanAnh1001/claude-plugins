"""Live Claude sessions and transcript discovery (never touches *.key)."""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import List, Optional, Tuple

from hh_ps.claude_source import pid_alive, slugify
from hh_ps.constants import (
    PROJECTS_SUBDIR, SESSIONS_SUBDIR, TRANSCRIPT_SUFFIX, TRANSCRIPT_TITLE_TYPE,
)

from .constants import SESSION_ENTRYPOINT_TUI, TRANSCRIPT_USER_TYPE
from .models import LiveSession, Transcript
from .paths import claude_dir, read_json


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def live_sessions() -> List[LiveSession]:
    folder = claude_dir() / SESSIONS_SUBDIR
    if not folder.is_dir():
        return []
    found: List[LiveSession] = []
    for path in sorted(folder.glob("*.json")):
        raw = read_json(path)
        if raw is None:
            continue
        pid = _as_int(raw.get("pid"))
        session_id = raw.get("sessionId")
        if not pid or not isinstance(session_id, str) or not session_id:
            continue
        if not pid_alive(pid):
            continue
        found.append(LiveSession(
            pid=pid,
            session_id=session_id,
            cwd=raw.get("cwd") if isinstance(raw.get("cwd"), str) else "",
            entrypoint=(raw.get("entrypoint")
                        if isinstance(raw.get("entrypoint"), str) else ""),
            status=raw.get("status") if isinstance(raw.get("status"), str) else "",
        ))
    return found


def tui_pids(session_id: str,
             sessions: Optional[List[LiveSession]] = None) -> List[int]:
    current = sessions if sessions is not None else live_sessions()
    return sorted({item.pid for item in current
                   if item.session_id == session_id
                   and item.entrypoint == SESSION_ENTRYPOINT_TUI})


def live_session_cwd(session_id: str,
                     sessions: Optional[List[LiveSession]] = None) -> str:
    current = sessions if sessions is not None else live_sessions()
    for item in current:
        if item.session_id == session_id and item.cwd:
            return item.cwd
    return ""


def _scan_transcript(path: Path, *, stop_early: bool = False,
                     mtime: Optional[float] = None) -> Optional[Transcript]:
    if mtime is None:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
    cwd = ""
    title = ""
    has_user = False
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(item, dict):
                    continue
                found_cwd = item.get("cwd")
                if isinstance(found_cwd, str) and found_cwd:
                    cwd = found_cwd
                if item.get("type") == TRANSCRIPT_USER_TYPE:
                    has_user = True
                elif item.get("type") == TRANSCRIPT_TITLE_TYPE:
                    found_title = item.get("customTitle")
                    if isinstance(found_title, str) and found_title:
                        title = found_title
                if stop_early and cwd and has_user:
                    break
    except OSError:
        return None
    return Transcript(session_id=path.stem, path=path, cwd=cwd,
                      has_user=has_user, mtime=mtime, title=title)


def read_custom_title(path: Path) -> str:
    """Last `customTitle` line in one transcript, parsing only those lines."""
    title = ""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if TRANSCRIPT_TITLE_TYPE not in line:
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(item, dict):
                    continue
                found = item.get("customTitle")
                if (item.get("type") == TRANSCRIPT_TITLE_TYPE
                        and isinstance(found, str) and found):
                    title = found
    except OSError:
        return ""
    return title


def transcripts() -> List[Transcript]:
    folder = claude_dir() / PROJECTS_SUBDIR
    if not folder.is_dir():
        return []
    found: List[Transcript] = []
    for path in folder.glob(f"*/*{TRANSCRIPT_SUFFIX}"):
        scanned = _scan_transcript(path)
        if scanned is not None:
            found.append(scanned)
    return found


def _transcript_paths(session_id: str) -> List[Path]:
    folder = claude_dir() / PROJECTS_SUBDIR
    if not folder.is_dir() or not session_id:
        return []
    pattern = f"*/{glob.escape(session_id)}{TRANSCRIPT_SUFFIX}"
    try:
        return [path for path in folder.glob(pattern) if path.is_file()]
    except OSError:
        return []


def find_transcript(session_id: str,
                    items: Optional[List[Transcript]] = None) -> Optional[Transcript]:
    if items is not None:
        matches = [item for item in items if item.session_id == session_id]
        if not matches:
            return None
        return max(matches, key=lambda item: (item.mtime, str(item.path)))
    best: Optional[Transcript] = None
    for path in _transcript_paths(session_id):
        scanned = _scan_transcript(path, stop_early=True)
        if scanned is None:
            continue
        if best is None or (scanned.mtime, str(scanned.path)) > (
                best.mtime, str(best.path)):
            best = scanned
    return best


def _in_project(cwd: str, slug: str, root: Path) -> bool:
    if cwd:
        try:
            path = Path(cwd).resolve()
        except (OSError, RuntimeError):
            return False
        return path == root or root in path.parents
    root_slug = slugify(root)
    return slug == root_slug or slug.startswith(root_slug + "-")


def _slug_matches(slug: str, root_slug: str) -> bool:
    return slug == root_slug or slug.startswith(root_slug + "-")


def _candidates(root: Path) -> List[Tuple[float, Path]]:
    folder = claude_dir() / PROJECTS_SUBDIR
    if not folder.is_dir():
        return []
    root_slug = slugify(root)
    try:
        project_dirs = [path for path in folder.iterdir()
                        if path.is_dir() and _slug_matches(path.name, root_slug)]
    except OSError:
        return []
    found: List[Tuple[float, Path]] = []
    for project_dir in project_dirs:
        for path in project_dir.glob(f"*{TRANSCRIPT_SUFFIX}"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            found.append((mtime, path))
    found.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
    return found


def newest_project_transcript(root: Path,
                              items: Optional[List[Transcript]] = None
                              ) -> Optional[Transcript]:
    if items is not None:
        candidates = [item for item in items
                      if item.has_user
                      and _in_project(item.cwd, item.path.parent.name, root)]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item.mtime, str(item.path)))
    for mtime, path in _candidates(root):
        scanned = _scan_transcript(path, stop_early=True, mtime=mtime)
        if scanned is None or not scanned.has_user:
            continue
        if scanned.cwd and _in_project(scanned.cwd, path.parent.name, root):
            return scanned
    return None
