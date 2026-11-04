"""Per-backend quota state {backend: {exhausted_until, used_percent, updated}} (fcntl-locked)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, Optional

from .backends.base import Quota
from .constants import DEFAULT_QUOTA_BACKOFF_HOURS
from .locked_json import locked, read_json, write_atomic


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def parse_iso(text: Optional[str]) -> Optional[dt.datetime]:
    if not text:
        return None
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)


def read_state(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.is_file():
        return {}
    with locked(path):
        return read_json(path, {})


def record(path: Path, backend: str, quota: Optional[Quota], exhausted: bool) -> None:
    """Store latest used_percent; on exhaustion set exhausted_until (resets_at or +backoff)."""
    now = utc_now()
    with locked(path):
        state = read_json(path, {})
        entry = dict(state.get(backend, {}))
        entry["updated"] = iso(now)
        if quota is not None and quota.used_percent is not None:
            entry["used_percent"] = quota.used_percent
        if exhausted:
            until = parse_iso(quota.resets_at if quota else None)
            if until is None or until <= now:
                until = now + dt.timedelta(hours=DEFAULT_QUOTA_BACKOFF_HOURS)
            entry["exhausted_until"] = iso(until)
        state[backend] = entry
        write_atomic(path, state)


def exhausted_until(path: Path, backend: str) -> Optional[dt.datetime]:
    """Future moment the backend's quota resets, or None when usable now."""
    until = parse_iso(read_state(path).get(backend, {}).get("exhausted_until"))
    return until if until and until > utc_now() else None
