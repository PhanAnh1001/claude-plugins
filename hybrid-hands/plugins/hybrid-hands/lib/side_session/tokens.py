"""Count tokens used by a side session.

Claude sessions can use the status-line token file configured as
`side_session.token_file` (one non-negative integer); otherwise the transcript is summed
over unique assistant message ids of input_tokens + cache_creation_input_tokens +
output_tokens (cache_read_input_tokens NOT counted). Codex = last `token_count` event
in the rollout file: input_tokens - cached_input_tokens + output_tokens (cache reads
NOT counted).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import constants as C


def project_slug(directory: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", directory)


def claude_transcript(directory: str, uuid: str, projects_dir: Path | None = None) -> Path:
    base = projects_dir or Path(os.environ.get(C.CLAUDE_PROJECTS_ENV, C.CLAUDE_PROJECTS_DIR)).expanduser()
    return base / project_slug(directory) / f"{uuid}.jsonl"


def _iter_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # partial last line while the session writes


def claude_tokens(path: Path) -> int:
    if not path.is_file():
        return 0
    per_msg: dict[str, int] = {}
    for rec in _iter_json(path):
        msg = rec.get("message") or {}
        usage = msg.get("usage")
        if rec.get("type") != "assistant" or not usage:
            continue
        total = (usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                 + usage.get("output_tokens", 0))
        key = msg.get("id") or rec.get("uuid") or str(len(per_msg))
        per_msg[key] = max(per_msg.get(key, 0), total)  # same id repeats per content block
    return sum(per_msg.values())


def token_file_tokens(template: str, uuid: str) -> int:
    """Read the status-line counter; missing, unreadable or malformed files count as 0."""
    path = Path(template.replace(C.TOKEN_FILE_PLACEHOLDER, uuid))
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return 0
    if not raw or not raw.isascii() or not raw.isdecimal():
        return 0
    return int(raw)


def codex_rollout(codex_home: Path, uuid: str, since: float = 0.0) -> Path | None:
    """Newest rollout touched at/after `since` (session start), so rollouts of other
    runs sharing this CODEX_HOME (e.g. hand-ext) that ended earlier are not counted."""
    root = codex_home / C.CODEX_SESSIONS_SUBDIR
    if not root.is_dir():
        return None
    hits = sorted((p for p in root.rglob(C.CODEX_ROLLOUT_GLOB) if p.stat().st_mtime >= since),
                  key=lambda p: p.stat().st_mtime)
    tagged = [p for p in hits if uuid in p.name]
    return (tagged or hits or [None])[-1]


def codex_tokens(path: Path | None) -> int:
    if path is None or not path.is_file():
        return 0
    last = 0
    for rec in _iter_json(path):
        payload = rec.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        usage = info.get("total_token_usage") or {}
        total_input = int(usage.get("input_tokens") or 0)
        cached = int(usage.get("cached_input_tokens") or 0)
        output = int(usage.get("output_tokens") or 0)
        last = max(0, total_input - cached + output)
    return last
