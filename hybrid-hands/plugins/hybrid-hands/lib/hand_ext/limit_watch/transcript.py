"""Detect a Claude Code quota stop from the session transcript's error flags.

Claude Code ends a turn that hit the 5-hour limit with a synthetic assistant
entry (``isApiErrorMessage`` true, ``error`` "rate_limit") instead of failing
the turn, so Paseo reports an ordinary idle agent without ``lastError``. Only
the flags, timestamp and the reset clock of that last entry are read; no
other transcript content leaves this module.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Enough for the last few entries; one tool result line can be large.
TAIL_BYTES = 1_000_000
QUOTA_ERROR = 'rate_limit'
CONVERSATION_TYPES = ('user', 'assistant')
# Claude Code text: "You've hit your 5-hour limit · resets 10:50am (Asia/Saigon)".
RESET_CLOCK = re.compile(r'resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*\(([^)]+)\)', re.I)
NOON_HOURS = 12


@dataclass(frozen=True)
class QuotaStop:
    blocked_at: float
    reset_at: Optional[float]


def transcript_path(home: Path, cwd: str, native_id: str) -> Optional[Path]:
    projects = Path(home) / 'projects'
    direct = projects / re.sub(r'[^A-Za-z0-9]', '-', cwd) / (native_id + '.jsonl')
    if direct.is_file():
        return direct
    return next(iter(sorted(projects.glob('*/' + native_id + '.jsonl'))), None)


def _tail_entries(path: Path):
    with path.open('rb') as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - TAIL_BYTES))
        lines = fh.read().splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # first line may be cut by the seek
        if isinstance(entry, dict):
            yield entry


def _epoch(stamp: object) -> Optional[float]:
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def _text(entry: dict) -> str:
    content = (entry.get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(str(p.get('text', '')) for p in content if isinstance(p, dict))
    return ''


def reset_epoch(text: str, blocked_at: float) -> Optional[float]:
    """First occurrence of the announced wall-clock time after the block."""
    match = RESET_CLOCK.search(text)
    if not match:
        return None
    hour, minute, half, zone = match.groups()
    try:
        tz = ZoneInfo(zone.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None
    hour24 = int(hour) % NOON_HOURS + (NOON_HOURS if half.lower() == 'pm' else 0)
    start = datetime.fromtimestamp(blocked_at, tz)
    reset = start.replace(hour=hour24, minute=int(minute or 0), second=0, microsecond=0)
    if reset <= start:
        reset += timedelta(days=1)
    return reset.timestamp()


def last_quota_stop(home: Path, cwd: str, native_id: str) -> Optional[QuotaStop]:
    """The main chain's last conversation entry, if it is a quota error."""
    path = transcript_path(home, cwd, native_id)
    if path is None:
        return None
    for entry in _tail_entries(path):
        if entry.get('isSidechain') or entry.get('type') not in CONVERSATION_TYPES:
            continue
        if not (entry.get('isApiErrorMessage') and entry.get('error') == QUOTA_ERROR):
            return None
        at = _epoch(entry.get('timestamp'))
        return None if at is None else QuotaStop(at, reset_epoch(_text(entry), at))
    return None
