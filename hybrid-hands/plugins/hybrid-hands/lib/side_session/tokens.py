"""Count tokens used by a side session.

Claude sessions can use the status-line token file configured as
`side_session.token_file` (one non-negative integer); otherwise the transcript is summed
over unique assistant message ids of input_tokens + cache_creation_input_tokens +
output_tokens (cache_read_input_tokens NOT counted). Codex = last `token_count` event
in the rollout file: input_tokens - cached_input_tokens + output_tokens (cache reads
NOT counted). Current Codex context includes cached input and output from last_token_usage.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import constants as C

CODEX_SESSION_META_TYPE = "session_meta"


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


def _session_meta(path: Path) -> dict:
    """First JSON record of a rollout; session_meta is always its first line."""
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                return record if isinstance(record, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return {}


def _created_at(meta: dict) -> float | None:
    """Creation time from the session_meta timestamp, never the rollout mtime."""
    payload = meta.get("payload")
    raw = meta.get("timestamp") or (payload.get("timestamp") if isinstance(payload, dict) else None)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (created if created.tzinfo else created.replace(tzinfo=timezone.utc)).timestamp()


def _same_dir(raw_cwd: object, workdir: str) -> bool:
    """Compare normalised paths so /tmp and /private/tmp are the same directory."""
    return (isinstance(raw_cwd, str) and bool(raw_cwd)
            and os.path.realpath(os.path.expanduser(raw_cwd))
            == os.path.realpath(os.path.expanduser(workdir)))


def codex_rollout(codex_home: Path, workdir: str, since: float = 0.0) -> Path | None:
    """Earliest rollout created at/after `since` whose session_meta cwd is `workdir`.

    Creation time comes from the session_meta timestamp: a running session keeps
    appending and updates the file mtime, so mtime is not its creation time. No
    uuid or newest-file fallback, because rollouts of other hands sharing this
    CODEX_HOME must never be counted for this session.
    """
    root = codex_home / C.CODEX_SESSIONS_SUBDIR
    if not root.is_dir():
        return None
    candidates: list[tuple[float, str, Path]] = []
    for path in root.rglob(C.CODEX_ROLLOUT_GLOB):
        meta = _session_meta(path)
        payload = meta.get("payload")
        if meta.get("type") != CODEX_SESSION_META_TYPE or not isinstance(payload, dict):
            continue
        if not _same_dir(payload.get("cwd"), workdir):
            continue
        created = _created_at(meta)
        if created is not None and created >= since:
            candidates.append((created, str(path), path))
    return min(candidates, key=lambda item: item[:2])[2].resolve() if candidates else None


def _codex_usage(path: Path | None, usage_key: str) -> dict:
    """Read the requested usage from the last token_count, ignoring other events.

    A missing usage on the latest event means unknown (zero), not stale usage
    from before native compaction. A partial JSON line is skipped by _iter_json.
    """
    if path is None or not path.is_file():
        return {}
    last: dict = {}
    for rec in _iter_json(path):
        payload = rec.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        last = info.get(usage_key) or {}
    return last


def codex_tokens(path: Path | None) -> int:
    """Cumulative non-cached usage for spending reports only."""
    usage = _codex_usage(path, "total_token_usage")
    total_input = int(usage.get("input_tokens") or 0)
    cached = int(usage.get("cached_input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    return max(0, total_input - cached + output)


def codex_context_tokens(path: Path | None) -> int:
    """Current context; input_tokens already includes cached_input_tokens.

    Do not subtract cache or use model_context_window: the displayed threshold
    is the native auto-compaction limit explicitly passed in the Codex argv.
    """
    # Missing last_token_usage must not fall back to cumulative total_token_usage.
    # That total can exceed the context threshold many times in a long session.
    usage = _codex_usage(path, "last_token_usage")
    total_input = int(usage.get("input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    return max(0, total_input + output)
