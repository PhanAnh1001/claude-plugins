#!/usr/bin/env python3
"""Split the Claude account's 7-day usage % into "this machine" and "other machines", in USD.

The statusLine payload only carries the account-wide 7-day percentage. week-split.sh records one
sample (epoch, pct, reset) per render; this script (run detached) prices this machine's API calls
from the local transcripts (usage_ledger.py), calibrates USD per 1 % from daily time windows when
only this machine runs, and converts this machine's USD in the current window to a percentage.
It also groups sessions under their main session (subagents share its id; claude side sessions
hang below it) with Claude and OpenCode Go usage (go_sessions.py), and estimates the 7-day % to
0.1 (the payload's integer plus this machine's USD since it last changed, capped at p + 0.9).

Ported from live-tiktok-games sessions/ops/runs/calibrate.sh (solo windows, MIN_DELTA_PCT,
PRIOR_USD_PER_PCT, unfinished and nested windows dropped, per-day extra windows) and
sessions/ops/runs/day-budget.sh (machine % = USD / usd_per_pct).

Writes $CLAUDE_HOME/.statusline-week-split.json for week-split.sh to print. Always exits 0.
"""
from __future__ import annotations

import json
import os
import sys
import time
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import accumulate
from pathlib import Path
from typing import Optional

from go_sessions import (GoWeek, build_groups, go_week_summary, group_total, load_go_week,
                         state_dir)
from usage_ledger import (DAY_SECONDS, RETENTION_SECONDS, session_name, update_ledger,
                          write_atomic)

SUMMARY_VERSION = 2
WEEK_SECONDS = 7 * DAY_SECONDS
# Rate-limit reset times jitter; two samples belong to the same window within this distance.
SAME_WINDOW_SECONDS = 3600
# A lock younger than this means another run is in progress.
LOCK_STALE_SECONDS = 300
LOOKBACK_DAYS = 7
# The payload percentage is an integer: below 2 points the rounding error dominates.
MIN_DELTA_PCT = 2
# Inferred from a rough first measurement ($9-15 per 1 % of the week).
PRIOR_USD_PER_PCT = 12.0
RATE_CALIB = "calib"
RATE_PRIOR = "prior"
# A USD-per-1% value pinned by the user: wins over calibration and the prior.
RATE_PIN = "pin"
# Daily windows (machine time) when only this machine runs; "-" = starts the day before.
DEFAULT_SOLO_WINDOWS = ("12:00-13:30", "-21:00-07:00")
DAILY_KEYWORD = "daily"
PREVIOUS_DAY_PREFIX = "-"
# Monday = 0 (datetime.weekday()).
WEEKDAY_LABELS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
# Claude truncates its integer %: the hidden fraction is below 1, so an estimate stays under p + 0.9.
ESTIMATE_MAX_FRACTION = 0.9
ESTIMATE_DECIMALS = 1
# A sample line has epoch, pct and reset; extra columns (old 5-hour data) are ignored.
SAMPLE_COLUMNS = 3
SIDE_PROVIDER_CLAUDE = "claude"
HYBRID_HANDS_CONFIG = Path(".claude") / "hybrid-hands.json"
DEFAULT_SIDE_STATE_DIR = "output/llm/side-sessions"

SAMPLES_NAME = ".statusline-week-samples.tsv"
SUMMARY_NAME = ".statusline-week-split.json"
LOCK_NAME = ".statusline-week-split.lock"
SOLO_WINDOWS_NAME = "statusline-solo-windows.txt"
# One positive number (USD per 1 % of the week); "#" lines are comments. Delete to unpin.
USD_PER_PCT_PIN_NAME = "statusline-usd-per-pct.txt"


@dataclass(frozen=True)
class Sample:
    t: float
    pct: float
    reset: float


@dataclass(frozen=True)
class Window:
    start: float
    end: float


@dataclass(frozen=True)
class DailySpec:
    start: str
    end: str
    from_previous_day: bool


@dataclass(frozen=True)
class Rate:
    usd_per_pct: float
    label: str
    n: int


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME") or Path.home() / ".claude")


# --- Samples ---
def parse_sample(line: str) -> Optional[Sample]:
    parts = line.strip().split("\t")
    if len(parts) < SAMPLE_COLUMNS:
        return None
    try:
        return Sample(*(float(part) for part in parts[:SAMPLE_COLUMNS]))
    except ValueError:
        return None


def load_samples(path: Path, now: float) -> list[Sample]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    samples = sorted((s for s in map(parse_sample, lines) if s is not None), key=lambda s: s.t)
    cutoff = now - RETENTION_SECONDS
    if samples and samples[0].t < cutoff:
        samples = [s for s in samples if s.t >= cutoff]
        text = "".join(f"{s.t:.0f}\t{s.pct:g}\t{s.reset:.0f}\n" for s in samples)
        write_atomic(path, text)  # rewritten with 3 columns
    return samples


# --- USD index ---
class UsdIndex:
    """Messages sorted by time with prefix sums: USD in [start, end) in O(log n)."""

    def __init__(self, messages: dict) -> None:
        rows = sorted((m[0], m[1]) for m in messages.values())
        self.times = [row[0] for row in rows]
        self.usd = [row[1] for row in rows]
        self.prefix = [0.0, *accumulate(self.usd)]

    def total(self, start: float, end: float = float("inf")) -> float:
        low, high = bisect_left(self.times, start), bisect_left(self.times, end)
        return self.prefix[high] - self.prefix[low] if high > low else 0.0

    def by_weekday(self, start: float) -> dict[int, float]:
        result: dict[int, float] = {}
        for i in range(bisect_left(self.times, start), len(self.times)):
            weekday = datetime.fromtimestamp(self.times[i]).weekday()
            result[weekday] = result.get(weekday, 0.0) + self.usd[i]
        return result


# --- Solo windows ---
def parse_range(text: str) -> Optional[tuple[str, str]]:
    start, sep, end = text.partition("-")
    try:
        datetime.strptime(start, "%H:%M"), datetime.strptime(end, "%H:%M")
    except ValueError:
        return None
    return (start, end) if sep else None


def parse_daily(text: str) -> Optional[DailySpec]:
    previous = text.startswith(PREVIOUS_DAY_PREFIX)
    parsed = parse_range(text[1:] if previous else text)
    return DailySpec(parsed[0], parsed[1], previous) if parsed else None


def load_solo_config(path: Path) -> tuple[list[DailySpec], list[tuple[date, str, str]]]:
    """(daily specs, one-day windows) from the config file; defaults when it has no daily line."""
    daily: list[DailySpec] = []
    extra: list[tuple[date, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for raw in lines:
        parts = raw.split()
        if len(parts) != 2 or parts[0].startswith("#"):
            continue
        if parts[0] == DAILY_KEYWORD:
            spec = parse_daily(parts[1])
            if spec:
                daily.append(spec)
            continue
        parsed = parse_range(parts[1])
        try:
            day = date.fromisoformat(parts[0])
        except ValueError:
            continue
        if parsed:
            extra.append((day, parsed[0], parsed[1]))
    if not daily:
        daily = [spec for spec in map(parse_daily, DEFAULT_SOLO_WINDOWS) if spec]
    return daily, extra


def at(day: date, hhmm: str) -> float:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time()).timestamp()


def solo_windows(config: Path, now: float) -> list[Window]:
    daily, extra = load_solo_config(config)
    today = datetime.fromtimestamp(now).date()
    candidates: list[Window] = []
    for i in range(LOOKBACK_DAYS + 1):
        day = today - timedelta(days=i)
        for spec in daily:
            start_day = day - timedelta(days=1) if spec.from_previous_day else day
            candidates.append(Window(at(start_day, spec.start), at(day, spec.end)))
    candidates.extend(Window(at(day, start), at(day, end)) for day, start, end in extra)
    return drop_unfinished_and_nested(candidates, now)


def drop_unfinished_and_nested(windows: list[Window], now: float) -> list[Window]:
    kept = []
    for i, inner in enumerate(windows):
        if inner.end > now:
            continue
        nested = any(j != i and outer.start <= inner.start and outer.end >= inner.end
                     and (outer != inner or j < i) for j, outer in enumerate(windows))
        if not nested:
            kept.append(inner)
    return kept


# --- Calibration ---
def same_window(a: Sample, b: Sample) -> bool:
    return abs(a.reset - b.reset) <= SAME_WINDOW_SECONDS


def window_delta(samples: list[Sample], window: Window) -> Optional[tuple[Sample, Sample]]:
    inside = [s for s in samples if window.start <= s.t <= window.end]
    if not inside:
        return None
    first = inside[0]
    last = [s for s in inside if same_window(s, first)][-1]
    return first, last


def load_pin(path: Path) -> Optional[float]:
    """The pinned USD per 1 %, or None when the file is missing or holds no positive number."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            value = float(text)
        except ValueError:
            return None
        return value if value > 0 else None
    return None


def calibrate(samples: list[Sample], index: UsdIndex, windows: list[Window],
              pin: Optional[float] = None) -> Rate:
    if pin is not None:
        return Rate(pin, RATE_PIN, 0)
    total_usd = 0.0
    total_delta = 0.0
    n = 0
    for window in windows:
        pair = window_delta(samples, window)
        if pair is None:
            continue
        first, last = pair
        delta = last.pct - first.pct
        if delta < MIN_DELTA_PCT:
            continue
        total_usd += index.total(first.t, last.t)
        total_delta += delta
        n += 1
    if n == 0 or total_delta <= 0:
        return Rate(PRIOR_USD_PER_PCT, RATE_PRIOR, 0)
    return Rate(round(total_usd / total_delta, 2), RATE_CALIB, n)


def estimate_week(samples: list[Sample], index: UsdIndex, now: float, rate: Rate) -> dict:
    """Integer % plus this machine's USD since it last changed, clamped to [p, p + 0.9]."""
    latest = samples[-1]
    t0 = latest.t
    for sample in reversed(samples):
        if sample.pct != latest.pct or not same_window(sample, latest):
            break
        t0 = sample.t
    raw = latest.pct + index.total(t0, now) / rate.usd_per_pct
    pct = min(max(raw, latest.pct), latest.pct + ESTIMATE_MAX_FRACTION)
    return {"pct": round(pct, ESTIMATE_DECIMALS), "base": latest.pct, "reset": int(latest.reset),
            "label": rate.label}


# --- Sessions ---
def find_repo(cwd: str) -> Optional[Path]:
    if not cwd:
        return None
    path = Path(cwd)
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def side_state_dir(repo: Path) -> Path:
    try:
        config = json.loads((repo / HYBRID_HANDS_CONFIG).read_text(encoding="utf-8"))
        state_dir = config["side_session"]["state_dir"]
        if isinstance(state_dir, str) and state_dir:
            return repo / state_dir
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return repo / DEFAULT_SIDE_STATE_DIR


def side_session_edges(repo: Path) -> list[tuple[str, str]]:
    """(parent session, child session) of claude side sessions recorded in one repo."""
    edges = []
    try:
        states = sorted(side_state_dir(repo).glob("*.json"))
    except OSError:
        return []
    for path in states:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(state, dict) or state.get("provider") != SIDE_PROVIDER_CLAUDE:
            continue
        child, parent = state.get("uuid"), state.get("parent_session")
        if isinstance(child, str) and child and isinstance(parent, str) and parent:
            edges.append((parent, child))
    return edges


def own_usd(ledger: dict, start: float) -> dict[str, float]:
    own: dict[str, float] = {}
    for ts, usd, sid in ledger["messages"].values():
        if ts >= start:
            own[sid] = own.get(sid, 0.0) + usd
    return own


def session_children(repos: set[Optional[Path]]) -> dict[str, set[str]]:
    children: dict[str, set[str]] = {}
    for repo in sorted(r for r in repos if r is not None):
        for parent, child in side_session_edges(repo):
            children.setdefault(parent, set()).add(child)
    return children


def ledger_repos(ledger: dict, sids: set[str]) -> set[Optional[Path]]:
    return {find_repo(ledger["sessions"].get(sid, {}).get("cwd", "")) for sid in sids}


def session_totals(ledger: dict, start: float, rate: float,
                   children: Optional[dict[str, set[str]]] = None) -> dict:
    own = own_usd(ledger, start)
    if children is None:
        children = session_children(ledger_repos(ledger, set(own)))
    result = {}
    for sid in set(own) | set(children):
        agg = group_total(sid, own, children)
        if agg > 0:
            result[sid] = {"usd": round(own.get(sid, 0.0), 4), "total_usd": round(agg, 4),
                           "pct": round(agg / rate, 2)}
    return result


# --- Summary ---
def weekday_order(start: float, now: float) -> list[int]:
    """Weekdays from the window start's to today's, in time order, each once."""
    day = datetime.fromtimestamp(start).date()
    last = datetime.fromtimestamp(max(start, now)).date()
    order: list[int] = []
    while day <= last:
        if day.weekday() not in order:
            order.append(day.weekday())
        day += timedelta(days=1)
    return order


def build_summary(samples: list[Sample], ledger: dict, now: float,
                  windows: Optional[list[Window]] = None,
                  go_week: Optional[GoWeek] = None,
                  pin: Optional[float] = None) -> Optional[dict]:
    if not samples:
        return None
    index = UsdIndex(ledger["messages"])
    rate = calibrate(samples, index, windows if windows is not None else [], pin)
    latest = samples[-1]
    start = latest.reset - WEEK_SECONDS
    local_usd = index.total(start)
    local = local_usd / rate.usd_per_pct
    weekday_usd = index.by_weekday(start)
    days = [{"wd": WEEKDAY_LABELS[wd], "pct": round(weekday_usd.get(wd, 0.0) / rate.usd_per_pct, 2)}
            for wd in weekday_order(start, now)]
    own = own_usd(ledger, start)
    repos = ledger_repos(ledger, set(own)) | {find_repo(run.cwd) for run in
                                              (go_week.runs if go_week else [])}
    children = session_children(repos)
    names = {sid: session_name(entry) for sid, entry in ledger["sessions"].items()}
    summary = {
        "version": SUMMARY_VERSION, "computed_at": int(now), "reset": int(latest.reset),
        "window_start": int(start), "total": latest.pct, "local": round(local, 2),
        "other": round(max(0.0, latest.pct - local), 2), "local_usd": round(local_usd, 4),
        "usd_per_pct": rate.usd_per_pct, "rate_label": rate.label, "calib_n": rate.n,
        "days": days, "sessions": session_totals(ledger, start, rate.usd_per_pct, children),
        "unpriced_models": sorted(ledger.get("unpriced", {})),
        "claude_estimates": {"week": estimate_week(samples, index, now, rate)},
        "groups": build_groups(own, children, rate.usd_per_pct, go_week, names),
    }
    if go_week is not None:
        summary["go_week"] = go_week_summary(go_week)
    return summary


# --- Lock and entry point ---
def acquire_lock(lock: Path, now: float) -> bool:
    try:
        lock.mkdir()
        return True
    except FileExistsError:
        pass
    try:
        if now - lock.stat().st_mtime < LOCK_STALE_SECONDS:
            return False
        os.utime(lock)  # take over the stale lock
        return True
    except OSError:
        return False


def run(home: Path, now: float, go_state: Optional[Path] = None) -> None:
    lock = home / LOCK_NAME
    if not acquire_lock(lock, now):
        return
    try:
        ledger = update_ledger(home, now)
        samples = load_samples(home / SAMPLES_NAME, now)
        windows = solo_windows(home / SOLO_WINDOWS_NAME, now)
        go_week = load_go_week(home, go_state or state_dir())
        summary = build_summary(samples, ledger, now, windows, go_week,
                                load_pin(home / USD_PER_PCT_PIN_NAME))
        if summary is not None:
            write_atomic(home / SUMMARY_NAME, json.dumps(summary, ensure_ascii=False))
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def main() -> int:
    try:
        run(claude_home(), time.time())
    except Exception as error:  # fail-open: the status line must never break
        print(f"week_split: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
