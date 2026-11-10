"""Time, size and path formatting helpers for `hh-ps`."""
from __future__ import annotations

import datetime as dt
import math
import os
import re
from pathlib import Path
from typing import Optional, Union

from .constants import ELLIPSIS, SINCE_UNITS

SINCE_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
MILLISECONDS = 1000.0


def parse_since(text: str) -> int:
    """`6h`, `90m`, `2d` (or seconds) to seconds; raises ValueError on bad input."""
    match = SINCE_RE.match(str(text).strip())
    if not match:
        raise ValueError("--since cần dạng <số><m|h|d>, ví dụ 6h")
    amount, unit = int(match.group(1)), match.group(2).lower()
    seconds = amount * SINCE_UNITS[unit]
    if seconds <= 0:
        raise ValueError("--since phải lớn hơn 0")
    return seconds


def to_epoch(value: Union[int, float, str, None]) -> Optional[float]:
    """Epoch seconds from a number (seconds or ms) or an ISO-8601 string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        return number / MILLISECONDS if number > 1e11 else number
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        number = None
    if number is not None:
        if not math.isfinite(number):
            return None
        return number / MILLISECONDS if number > 1e11 else number
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.timestamp()


def iso_at(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return dt.datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


END_SAME_DAY_FORMAT = "%H:%M"
END_OTHER_DAY_FORMAT = "%d/%m %H:%M"


def ended_text(epoch: Optional[float], now: float) -> Optional[str]:
    """`HH:MM` (same local day as `now`) or `dd/mm HH:MM`; the legend explains it."""
    if epoch is None:
        return None
    moment = dt.datetime.fromtimestamp(epoch)
    same_day = moment.date() == dt.datetime.fromtimestamp(now).date()
    fmt = END_SAME_DAY_FORMAT if same_day else END_OTHER_DAY_FORMAT
    return moment.strftime(fmt)


def duration_text(seconds: Optional[float]) -> Optional[str]:
    """Compact Vietnamese duration: 2ng, 2g3p, 45p, 30s."""
    if seconds is None:
        return None
    total = max(0, int(seconds))
    days, rest = divmod(total, SECONDS_PER_DAY)
    hours, rest = divmod(rest, SECONDS_PER_HOUR)
    minutes, secs = divmod(rest, SECONDS_PER_MINUTE)
    if days:
        return f"{days}ng"  # hours dropped past a day to keep the column narrow
    if hours:
        return f"{hours}g{minutes}p" if minutes else f"{hours}g"
    if minutes:
        return f"{minutes}p"
    return f"{secs}s"


def age_text(seconds: Optional[float]) -> Optional[str]:
    text = duration_text(seconds)
    return f"{text} trước" if text else None


THOUSAND = 1000
MILLION = 1_000_000
# Below this many thousands a `k` value keeps one decimal (6.4k); above it, none (46k).
K_DECIMAL_BELOW = 10


def token_text(count: Optional[int]) -> Optional[str]:
    """Compact count: 950, 6.4k, 46k, 1.2M."""
    if count is None:
        return None
    value = max(0, int(count))
    if value < THOUSAND:
        return str(value)
    thousands = value / THOUSAND
    if thousands < K_DECIMAL_BELOW:
        return _one_decimal(thousands) + "k"
    if round(thousands) < THOUSAND:
        return f"{round(thousands)}k"
    return _one_decimal(value / MILLION) + "M"


def _one_decimal(number: float) -> str:
    return f"{number:.1f}".rstrip("0").rstrip(".")


USD_DECIMALS = 2
USD_MIN_VISIBLE = 0.01


def usd_text(amount: Optional[float]) -> Optional[str]:
    """`$0.42`, `<$0.01` under one cent, `$0` for nothing used, None without estimate."""
    if amount is None:
        return None
    if amount <= 0:
        return "$0"
    if amount < USD_MIN_VISIBLE:
        return "<$0.01"
    return f"${amount:.{USD_DECIMALS}f}"


PERCENT_DECIMALS = 1
PERCENT_MIN_VISIBLE = 0.1


def percent_text(percent: Optional[float], estimated: bool = False) -> Optional[str]:
    """`12.3%` (one decimal), `<0.1%` for a tiny non-zero share, None when unknown.

    ``estimated`` prefixes the statusline's "~" mark.
    """
    if percent is None:
        return None
    mark = "~" if estimated else ""
    if 0 < percent < PERCENT_MIN_VISIBLE / 2:
        return f"{mark}<{PERCENT_MIN_VISIBLE}%"
    return f"{mark}{max(0.0, percent):.{PERCENT_DECIMALS}f}%"


def ratio_text(current: Optional[int], cap: Optional[int]) -> Optional[str]:
    if current is None or not cap or cap <= 0:
        return None
    percent = current / cap * 100
    text = f"{percent:.1f}".rstrip("0").rstrip(".")
    return text + "%"


def short_path(path: Optional[str], home: Optional[Path] = None) -> Optional[str]:
    if not path:
        return None
    home = (home or Path(os.path.expanduser("~"))).resolve()
    try:
        relative = Path(path).resolve().relative_to(home)
    except (OSError, RuntimeError, ValueError):
        return str(path)
    return "~" if str(relative) == "." else "~/" + str(relative)


def truncate(text: Optional[str], limit: int) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit - 1] + ELLIPSIS
