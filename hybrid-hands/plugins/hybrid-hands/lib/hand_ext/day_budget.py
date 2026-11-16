"""This machine's Claude day use: USD since local midnight over the weekly USD per 1 %.

USD comes from the statusline plugin's `usage_ledger.window_messages`, loaded exactly like
`hh_ps/week.py` does (its loader and price table, never a copy). USD per 1 % is the user's
pin in `<claude home>/statusline-usd-per-pct.txt`, else statusline's calibrated rate from
`<claude home>/.statusline-week-split.json`. Missing data is not an estimate: callers must
fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from hh_ps import week as statusline_week

from .constants import CLAUDE_MAIN_CONFIG_DIR, CLAUDE_MAIN_MAX_DAY_PCT

USD_PER_PCT_PIN = "statusline-usd-per-pct.txt"
WEEK_SPLIT_SUMMARY = ".statusline-week-split.json"


class BudgetUnavailable(Exception):
    """The day percentage cannot be computed; the caller must stop the run."""


@dataclass(frozen=True)
class DayUsage:
    usd: float
    usd_per_pct: float
    pct: float
    max_pct: float

    @property
    def blocked(self) -> bool:
        return self.pct >= self.max_pct


def _positive(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def local_midnight(now: float) -> float:
    """00:00 today in machine time, as epoch seconds."""
    today = dt.datetime.fromtimestamp(now).astimezone()
    return today.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def claude_home(options: dict) -> Path:
    raw = options.get("config_dir") or CLAUDE_MAIN_CONFIG_DIR
    return Path(os.path.expanduser(str(raw))).resolve()


def _pin(home: Path) -> Optional[float]:
    try:
        lines = (home / USD_PER_PCT_PIN).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        return _positive(text)
    return None


def _calibrated(home: Path) -> Optional[float]:
    try:
        data = json.loads((home / WEEK_SPLIT_SUMMARY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("rate_label") not in statusline_week.TRUSTED_RATE_LABELS:
        return None
    return _positive(data.get("usd_per_pct"))


def usd_per_pct(home: Path) -> Optional[float]:
    """Pinned USD per 1 % first, then statusline's calibrated rate."""
    return _pin(home) or _calibrated(home)


DAY_GUARD_DAYS_KEY = "day_guard_days"
# Local weekday names in datetime.weekday() order (Monday = 0).
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class DayGuardConfigError(ValueError):
    """`day_guard_days` is not a list of `mon..sun` names."""


def _local_day(now: Optional[float]) -> dt.date:
    moment = time.time() if now is None else now
    return dt.datetime.fromtimestamp(local_midnight(moment)).astimezone().date()


def guard_days(options: dict) -> Optional[frozenset]:
    """Weekdays the guard applies on; None (missing or empty list) means every day."""
    raw = options.get(DAY_GUARD_DAYS_KEY)
    if raw is None:
        return None
    if not isinstance(raw, list) or any(day not in WEEKDAY_NAMES for day in raw):
        raise DayGuardConfigError(
            f"{DAY_GUARD_DAYS_KEY} phải là danh sách tên ngày trong {', '.join(WEEKDAY_NAMES)}"
            f" (nhận {raw!r})")
    return frozenset(raw) or None


def inactive_reason(options: dict, now: Optional[float] = None) -> Optional[str]:
    """Why the guard does not apply now, or None when it applies.

    Off when `day_guard` is exactly false, `day_guard_off_date` is today (local
    `YYYY-MM-DD`, back on the next day) or today is not in `day_guard_days`. Any other
    `day_guard`/off-date value, malformed included, keeps the guard on (fail closed); a
    malformed `day_guard_days` raises DayGuardConfigError.
    """
    if options.get("day_guard", True) is False:
        return "day_guard tắt"
    today = _local_day(now)
    off = options.get("day_guard_off_date")
    if isinstance(off, str) and off.strip() == today.isoformat():
        return f"day_guard_off_date tắt guard hôm nay ({today.isoformat()})"
    days = guard_days(options)
    name = WEEKDAY_NAMES[today.weekday()]
    if days is not None and name not in days:
        return (f"ngoài ngày áp dụng guard ({name} không thuộc "
                f"{DAY_GUARD_DAYS_KEY}={sorted(days, key=WEEKDAY_NAMES.index)})")
    return None


def guard_enabled(options: dict, now: Optional[float] = None) -> bool:
    """True when the day guard applies now (see `inactive_reason`)."""
    return inactive_reason(options, now) is None


def _max_pct(options: dict) -> float:
    value = _positive(options.get("max_day_pct", CLAUDE_MAIN_MAX_DAY_PCT))
    if value is None:
        raise BudgetUnavailable("max_day_pct phải là số dương")
    return value


def machine_usd(home: Path, since: float, until: float) -> float:
    """This machine's USD in [since, until], through statusline's own ledger and prices."""
    usd = statusline_week._fresh_ledger_usd(home, since, until)
    if usd is None:
        raise BudgetUnavailable("thiếu hoặc không đọc được usage_ledger.py của statusline")
    return usd


def assess(options: dict, now: Optional[float] = None) -> DayUsage:
    moment = time.time() if now is None else now
    home = claude_home(options)
    rate = usd_per_pct(home)
    if rate is None:
        raise BudgetUnavailable(
            f"thiếu USD/1% ({USD_PER_PCT_PIN} hoặc {WEEK_SPLIT_SUMMARY})")
    usd = machine_usd(home, local_midnight(moment), moment)
    return DayUsage(usd=usd, usd_per_pct=rate, pct=usd / rate,
                    max_pct=_max_pct(options))
