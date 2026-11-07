"""Đọc mẫu hạn mức sống do `claude-tee` ghi trong thư mục Claude."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .timeutil import to_epoch

STATE_NAME = ".hh-claude-rate-limit.json"
STATE_VERSION = 1
PERCENT = 100.0


@dataclass(frozen=True)
class LiveSample:
    pct: float
    resets_at: float
    ts: float


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_live_window(claude_home: Path, window: str, now: float) -> Optional[LiveSample]:
    """Mẫu mới nhất của một cửa sổ; None khi thiếu, hỏng, cũ hoặc đã reset."""
    try:
        data = json.loads((Path(claude_home) / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
        return None
    windows = data.get("windows")
    if not isinstance(windows, dict):
        return None
    entry = windows.get(window)
    if not isinstance(entry, dict):
        return None
    utilization = _number(entry.get("utilization"))
    resets_at = to_epoch(entry.get("resets_at"))
    ts = _number(entry.get("ts"))
    if utilization is None or resets_at is None or ts is None:
        return None
    if resets_at <= now or not 0 <= utilization <= 1 or not 0 <= now - ts < 1800:
        return None
    pct = max(0.0, min(PERCENT, utilization * PERCENT))
    return LiveSample(pct=pct, resets_at=resets_at, ts=ts)
