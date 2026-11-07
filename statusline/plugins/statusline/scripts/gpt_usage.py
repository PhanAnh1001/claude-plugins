"""GPT (Codex) cells for the statusline limit table.

Reads local shared Codex account samples (ledger and fixed .codex-hand rollouts).
Today's estimated USD remains ledger-only. Read-only, no network or credentials.
Missing shared sources fail open; collect() remains a deterministic ledger-only helper.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Iterator, Optional, Tuple

SCHEMA_VERSION = 1
CODEX_HOME = ".codex-hand"
LEDGER_NAME = "codex_usage.jsonl"
FRESH_SECONDS = 24 * 3600
PCT_MAX = 100
UNKNOWN_USD = "?"
USD_FORMAT = "{:.2f}"
CELL_SEPARATOR = "\x1f"


def ledger_path() -> Path:
    state_dir = os.environ.get("HYBRID_HANDS_STATE_DIR") or str(Path.home() / ".hybrid-hands")
    return Path(state_dir) / LEDGER_NAME


def finite_number(value: Any) -> Optional[float]:
    """A JSON number that is finite, not a bool and not negative, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return 0.0 if number == 0 else number


def parse_moment(value: Any) -> Optional[dt.datetime]:
    """An ISO-8601 string (any offset, optional Z) or an epoch number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = finite_number(value)
        if number is None:
            return None
        try:
            return dt.datetime.fromtimestamp(number, dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return moment


def is_account_record(record: Any) -> bool:
    """Schema 1 and the hand account only; `.codex` and unknown schemas are ignored."""
    if not isinstance(record, dict):
        return False
    schema = record.get("schema")
    return not isinstance(schema, bool) and schema == SCHEMA_VERSION \
        and record.get("codex_home") == CODEX_HOME


def read_records(path: Path) -> Iterator[dict]:
    """Yield JSON objects line by line; a broken line, scalar or list is skipped."""
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record


def window_percent(raw: Any, now: dt.datetime) -> Optional[float]:
    """A used_percent 0..100 whose reset is in the future; null/expired is not shown."""
    if not isinstance(raw, dict):
        return None
    percent = finite_number(raw.get("used_percent"))
    reset = parse_moment(raw.get("resets_at"))
    if percent is None or percent > PCT_MAX or reset is None or reset <= now:
        return None
    return percent


def collect(path: Path, now: dt.datetime) -> Optional[Tuple[Optional[float], Optional[float], str]]:
    """Newest quota sample plus today's USD, or None when the newest sample is >= 24h old."""
    today_start = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    sample_ended: Optional[dt.datetime] = None
    sample_windows: dict = {}
    usd_total = 0.0
    usd_unknown = False
    for record in read_records(path):
        if not is_account_record(record):
            continue
        ended = parse_moment(record.get("ended"))
        if ended is None or ended > now:
            continue
        windows = record.get("windows")
        if isinstance(windows, dict) and (sample_ended is None or ended > sample_ended):
            sample_ended = ended
            sample_windows = windows
        if ended >= today_start:
            cost = finite_number(record.get("cost_usd"))
            if cost is None:
                usd_unknown = True
            else:
                usd_total += cost
    if sample_ended is None or (now - sample_ended).total_seconds() >= FRESH_SECONDS:
        return None
    usd = UNKNOWN_USD if usd_unknown else USD_FORMAT.format(usd_total)
    return (window_percent(sample_windows.get("5h"), now),
            window_percent(sample_windows.get("7d"), now), usd)


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    data = collect(ledger_path(), now)
    from shared_usage import account_windows
    windows = account_windows(now.timestamp())
    # Keep the ledger's schema/freshness checks; compare each rollout window independently.
    latest = {}
    for record in read_records(ledger_path()):
        ended = parse_moment(record.get("ended")) if is_account_record(record) else None
        if ended is None or not 0 <= (now - ended).total_seconds() < FRESH_SECONDS:
            continue
        raw = record.get("windows")
        if not isinstance(raw, dict):
            continue
        for key, label in (("5h", "5h"), ("7d", "tuần")):
            if key in raw and (label not in latest or ended.timestamp() > latest[label][1]):
                latest[label] = (window_percent(raw[key], now), ended.timestamp())
    for label, sample in windows.items():
        if label not in latest or sample[1] >= latest[label][1]:
            latest[label] = sample
    if latest or data is not None:
        data = (latest.get("5h", (None,))[0], latest.get("tuần", (None,))[0],
                data[2] if data else UNKNOWN_USD)
    if data is None:
        return 0
    five, seven, usd = data
    cells = ("" if five is None else str(five), "" if seven is None else str(seven), usd)
    sys.stdout.write(CELL_SEPARATOR.join(cells) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
