"""GPT (Codex) cells for the statusline limit table, from the ~/.codex account's rollouts.

5h / 7d %: the newest `token_count.rate_limits` sample (by timestamp) in `sessions/` and
`archived_sessions/`. A window is labelled by `window_minutes` (300 = 5h, 10080 = 7d); a legacy
sample without durations keeps primary = 5h, secondary = 7d. Expired resets show "?".
Today's USD~: per-thread token deltas of today's (local) `token_count` events x the canonical
price file; an unpriced model or unreadable price file gives "?". Read-only, offline estimate.
Only rollouts modified within SCAN_DAYS are read. STATUSLINE_CODEX_DIR overrides ~/.codex.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

from shared_prices import load_prices

CODEX_DIR_ENV = "STATUSLINE_CODEX_DIR"
CODEX_DIR_NAME = ".codex"
ROLLOUT_DIRS = ("sessions", "archived_sessions")
ROLLOUT_GLOB = "rollout-*.jsonl"
SCAN_DAYS = 7
FRESH_SECONDS = 24 * 3600
PCT_MAX = 100
FIVE_HOUR_MINUTES = 300
WEEK_MINUTES = 10080
LEGACY_WINDOWS = {"primary": "5h", "secondary": "7d"}
TOKENS_PER_PRICE_UNIT = 1_000_000
UNKNOWN_USD = "?"
USD_FORMAT = "{:.2f}"
CELL_SEPARATOR = "\x1f"
EVENT_MARKER = '"token_count"'


def codex_dir() -> Path:
    return Path(os.environ.get(CODEX_DIR_ENV) or Path.home() / CODEX_DIR_NAME)


def finite_number(value: Any) -> Optional[float]:
    """A JSON number that is finite, not a bool and not negative, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)


def parse_moment(value: Any) -> Optional[dt.datetime]:
    """An ISO-8601 string (any offset, optional Z) or an epoch number, else None."""
    number = finite_number(value)
    if number is not None:
        try:
            return dt.datetime.fromtimestamp(number, dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.astimezone()


def recent_rollouts(root: Path, since: float) -> list[tuple[float, Path]]:
    """(mtime, path) of rollouts modified at or after `since`, newest first."""
    found = []
    for name in ROLLOUT_DIRS:
        for path in (root / name).rglob(ROLLOUT_GLOB):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= since:
                found.append((mtime, path))
    return sorted(found, reverse=True)


def read_events(path: Path) -> Iterator[tuple[str, dict, Optional[dt.datetime]]]:
    """(record type, payload, timestamp) of session_meta / turn_context / token_count lines."""
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            if EVENT_MARKER not in line and '"session_meta"' not in line \
                    and '"turn_context"' not in line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            payload = record.get("payload") if isinstance(record, dict) else None
            if isinstance(payload, dict):
                kind = payload.get("type") if record.get("type") == "event_msg" else record.get("type")
                yield str(kind), payload, parse_moment(record.get("timestamp"))


def sample_windows(rate_limits: dict, now: dt.datetime) -> dict:
    """{"5h"|"7d": (pct, reset epoch)} of usable windows; durations decide the label."""
    result = {}
    for slot, legacy in LEGACY_WINDOWS.items():
        raw = rate_limits.get(slot)
        if not isinstance(raw, dict):
            continue
        minutes = raw.get("window_minutes")
        label = {FIVE_HOUR_MINUTES: "5h", WEEK_MINUTES: "7d"}.get(minutes) if minutes is not None \
            else legacy
        pct = finite_number(raw.get("used_percent"))
        reset = parse_moment(raw.get("resets_at"))
        if label and pct is not None and pct <= PCT_MAX and reset is not None and reset > now:
            result[label] = (pct, int(reset.timestamp()))
    return result


def event_cost(delta: dict, model: Optional[str], prices: dict) -> Optional[float]:
    price = prices.get(model or "")
    if price is None:
        return None
    cached = delta.get("cached_input_tokens", 0)
    fresh = max(delta.get("input_tokens", 0) - cached, 0)
    output = delta.get("output_tokens", 0)
    return (fresh * price["input"] + cached * price["cached"] + output * price["output"]) \
        / TOKENS_PER_PRICE_UNIT


def token_delta(total: dict, previous: Optional[dict]) -> dict:
    keys = ("input_tokens", "cached_input_tokens", "output_tokens")
    current = {k: finite_number(total.get(k)) or 0 for k in keys}
    if previous is None or current["input_tokens"] < previous["input_tokens"]:
        return current
    return {k: max(current[k] - previous[k], 0) for k in keys}


def collect(root: Path, now: dt.datetime, prices: dict) -> Optional[tuple]:
    """(5h, 7d windows dict, today's USD text) or None without a sample in the last 24h."""
    today = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    files = recent_rollouts(root, now.timestamp() - SCAN_DAYS * 86400)
    newest: Optional[tuple] = None
    threads: dict = {}
    for mtime, path in files:
        need_usd = mtime >= today.timestamp()
        if not need_usd and newest is not None and mtime < newest[0].timestamp():
            break
        thread, model = path.stem, None
        for kind, payload, at in read_events(path):
            if kind == "session_meta":
                thread = str(payload.get("id") or thread)
            elif kind == "turn_context":
                model = payload.get("model") or model
            elif kind == "token_count" and at is not None and at <= now:
                limits = payload.get("rate_limits")
                if isinstance(limits, dict) and (newest is None or at > newest[0]):
                    newest = (at, limits)
                info = payload.get("info")
                total = info.get("total_token_usage") if isinstance(info, dict) else None
                if need_usd and isinstance(total, dict):
                    threads.setdefault(thread, {})[total.get("total_tokens")] = (at, total, model)
    if newest is None or (now - newest[0]).total_seconds() >= FRESH_SECONDS:
        return None
    return sample_windows(newest[1], now), today_usd(threads, today, prices)


def today_usd(threads: dict, today: dt.datetime, prices: dict) -> str:
    """Sum of today's per-thread deltas; duplicate totals (resumed copies) count once."""
    usd = 0.0
    for events in threads.values():
        previous = None
        for at, total, model in sorted(events.values(), key=lambda e: e[0]):
            delta = token_delta(total, previous)
            previous = {k: finite_number(total.get(k)) or 0 for k in delta}
            if at < today or not any(delta.values()):
                continue
            cost = event_cost(delta, model, prices)
            if cost is None:
                return UNKNOWN_USD
            usd += cost
    return USD_FORMAT.format(usd)


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    data = collect(codex_dir(), now, load_prices())
    if data is None:
        return 0
    windows, usd = data
    five = windows.get("5h", ("", ""))
    seven = windows.get("7d", ("", ""))
    # Cells: 5h %, 7d %, today's USD, 5h reset, 7d reset (epoch); "" when unknown.
    cells = (str(five[0]), str(seven[0]), usd, str(five[1]), str(seven[1]))
    sys.stdout.write(CELL_SEPARATOR.join(cells) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
