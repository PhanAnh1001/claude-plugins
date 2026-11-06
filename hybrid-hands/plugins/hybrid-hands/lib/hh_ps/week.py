"""Weekly plan windows for `hh-ps`, using the statusline plugin's formulas.

Ported from statusline plugins/statusline/scripts/week_split.py (Claude: calibrate,
``local = local_usd / usd_per_pct``, ``other = total - local``, the 0.1 estimate clamped
to ``[p, p + 0.9]``) and plugins/statusline/scripts/go_sessions.py (Go: the week starts
at the live cache's weekly reset minus seven days; a run counts when it ended inside
that window; ``pct = usd / week.limit_usd * 100``).

Only the weekly window is exposed: the 5-hour and monthly windows are intentionally
absent from `hh-ps` and both tree panels.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from hand_ext.constants import GO_USAGE_DEFAULT_PRICE
from hand_ext.go_usage import estimate_cost

from .models import Usage

DAY_SECONDS = 86400
WEEK_SECONDS = 7 * DAY_SECONDS
SAME_WINDOW_SECONDS = 3600
SUMMARY_STALE_SECONDS = 1800
GO_LIVE_STALE_SECONDS = 900
GO_LIVE_ERROR_KEEP_SECONDS = 21600
SUMMARY_VERSION = 2
RATE_CALIBRATED = "calib"
PERCENT = 100.0
GO_MODEL_MARKER = "deepseek"
GO_WEEK_KEY = "7d"
GO_USAGE_LOG_NAME = "go_usage.jsonl"
GO_SUMMARY_NAME = "go_usage_summary.json"
GO_LIVE_CACHE_NAME = ".statusline-go-usage.json"
CLAUDE_CACHE_NAME = ".statusline-cache.json"
CLAUDE_WEEK_SPLIT_NAME = ".statusline-week-split.json"
RUNS_SUBDIR = "runs"
RUN_STATUS_RUNNING = "running"
COST_EXACT = "exact"


@dataclass(frozen=True)
class GoWeek:
    """This machine's Go week and the account total shown by the statusline cache."""

    window_start: float
    limit_usd: float
    runs: List["GoWeekRun"]
    total_pct: Optional[float]
    resets_at: Optional[float]
    total_estimated: bool
    source: str

    @property
    def machine_usd(self) -> float:
        return sum(run.usd for run in self.runs)

    @property
    def machine_pct(self) -> Optional[float]:
        if self.limit_usd <= 0:
            return None
        return self.machine_usd / self.limit_usd * PERCENT


@dataclass(frozen=True)
class GoWeekRun:
    run_id: str
    usd: float
    parent_session: Optional[str]
    cwd: str
    estimated: bool
    ended_at: Optional[float]


@dataclass(frozen=True)
class ClaudeWeek:
    """The account week split from the statusline cache and week-split summary."""

    window_start: float
    total_pct: float
    this_machine_pct: Optional[float]
    other_pct: Optional[float]
    resets_at: Optional[float]
    usd_per_pct: Optional[float]
    total_estimated: bool
    split_estimated: bool
    source: str

    @property
    def estimated(self) -> bool:
        return self.total_estimated or self.split_estimated


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _number(value: Any) -> Optional[float]:
    """Finite non-negative number; the statusline cache stores numbers as strings."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _int(value: Any) -> Optional[int]:
    number = _number(value)
    return int(number) if number is not None else None


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


# --- Go week (statusline go_sessions.py) ---
def _go_summary(state: Path) -> Optional[Dict[str, Any]]:
    return read_json(state / GO_SUMMARY_NAME)


def _go_week_limit(state: Path) -> Optional[float]:
    summary = _go_summary(state) or {}
    models = summary.get("models")
    if not isinstance(models, dict):
        return None
    for name, windows in models.items():
        if GO_MODEL_MARKER in str(name).lower() and isinstance(windows, dict):
            week = windows.get(GO_WEEK_KEY)
            limit = _number(week.get("limit_usd")) if isinstance(week, dict) else None
            if limit and limit > 0:
                return limit
    return None


def _registry(state: Path) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    try:
        paths = sorted((state / RUNS_SUBDIR).glob("*.json"))
    except OSError:
        return found
    for path in paths:
        record = read_json(path)
        if record is not None:
            found[str(record.get("run_id") or path.stem)] = record
    return found


def _finished_runs(state: Path, start: float, registry: Dict[str, Dict[str, Any]]
                   ) -> tuple[List[GoWeekRun], set]:
    runs: List[GoWeekRun] = []
    logged: set = set()
    try:
        lines = (state / GO_USAGE_LOG_NAME).read_text(encoding="utf-8").splitlines()
    except OSError:
        return runs, logged
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or not record.get("run_id"):
            continue
        run_id = str(record["run_id"])
        logged.add(run_id)
        ended = _epoch(record.get("ended"))
        usd = _number(record.get("cost_usd"))
        if ended is None or ended < start or usd is None:
            continue
        entry = registry.get(run_id) or {}
        parent = entry.get("parent_session")
        cwd = entry.get("cwd")
        runs.append(GoWeekRun(
            run_id=run_id, usd=usd,
            parent_session=str(parent) if parent else None,
            cwd=str(cwd) if isinstance(cwd, str) else "",
            estimated=str(record.get("cost_source") or "") != COST_EXACT,
            ended_at=ended))
    return runs, logged


def _running_runs(registry: Dict[str, Dict[str, Any]], logged: set) -> List[GoWeekRun]:
    runs: List[GoWeekRun] = []
    for run_id, record in registry.items():
        if record.get("status") != RUN_STATUS_RUNNING or run_id in logged:
            continue
        usd = estimate_cost(record.get("tokens") or {}, GO_USAGE_DEFAULT_PRICE)
        runs.append(GoWeekRun(
            run_id=run_id, usd=float(usd or 0.0),
            parent_session=str(record["parent_session"])
            if record.get("parent_session") else None,
            cwd=str(record.get("cwd") or ""), estimated=True, ended_at=None))
    return runs


def _epoch(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.timestamp()


def _go_total(cache: Optional[Dict[str, Any]], now: float,
              state: Path) -> tuple[Optional[float], Optional[float], bool, str]:
    """(weekly percent, weekly reset, estimated, source) as the statusline reads it."""
    windows = (cache or {}).get("windows")
    windows = windows if isinstance(windows, dict) else {}
    weekly = windows.get("weekly") if isinstance(windows.get("weekly"), dict) else {}
    reset = _number(weekly.get("resets_at"))
    now_i = int(now)
    complete = all(isinstance(windows.get(name), dict)
                   and _number(windows[name].get("percent")) is not None
                   and _number(windows[name].get("resets_at")) is not None
                   for name in ("rolling", "weekly", "monthly"))
    fetch = _number((cache or {}).get("fetched_at"))
    last_ok = _number((cache or {}).get("last_ok_at"))
    state_name = (cache or {}).get("state")
    live_ok = False
    if complete and state_name == "ok" and fetch is not None:
        live_ok = True
    elif complete and state_name == "error" and last_ok is not None:
        live_ok = now_i - last_ok < GO_LIVE_ERROR_KEEP_SECONDS
    if live_ok:
        percent = _number(weekly.get("percent"))
        stale = (now_i - (last_ok or fetch or 0)) >= GO_LIVE_STALE_SECONDS
        if reset is not None and reset <= now:
            # Same as the statusline: an expired window has reset, so show ~0%.
            return 0.0, None, True, "go_live"
        return percent, reset, bool(stale), "go_live"
    summary = _go_summary(state) or {}
    models = summary.get("models") if isinstance(summary.get("models"), dict) else {}
    for name, model in models.items():
        if GO_MODEL_MARKER not in str(name).lower() or not isinstance(model, dict):
            continue
        week = model.get(GO_WEEK_KEY) if isinstance(model.get(GO_WEEK_KEY), dict) else {}
        percent = _number(week.get("percent"))
        if percent is None:
            continue
        updated = _number(summary.get("updated_at"))
        stale = (bool(week.get("estimated")) or updated is None
                 or now_i - int(updated) >= 5 * 3600)
        return percent, reset, stale, "ledger"
    return None, reset, True, "ledger"


def read_go_week(state: Path, claude_home: Path, now: float) -> Optional[GoWeek]:
    """This machine's Go week plus the account total, or None without a usable source."""
    cache = read_json(claude_home / GO_LIVE_CACHE_NAME)
    limit = _go_week_limit(state)
    windows = (cache or {}).get("windows")
    windows = windows if isinstance(windows, dict) else {}
    weekly = windows.get("weekly") if isinstance(windows.get("weekly"), dict) else {}
    reset = _number(weekly.get("resets_at"))
    total, live_reset, total_estimated, source = _go_total(cache, now, state)
    if total is None and not windows:
        return None
    start = (live_reset if live_reset is not None else now) - WEEK_SECONDS
    registry = _registry(state)
    finished, logged = _finished_runs(state, start, registry)
    runs = finished + _running_runs(registry, logged)
    return GoWeek(window_start=start, limit_usd=float(limit or 0.0), runs=runs,
                  total_pct=total, resets_at=live_reset,
                  total_estimated=total_estimated, source=source)



# --- Claude week (statusline week_split.py + week-split.sh) ---
def _week_split(state: Dict[str, Any], cache_reset: Optional[float], now: float
                ) -> tuple[Optional[Dict[str, Any]], bool]:
    """The summary when it describes the cache's window; (summary, stale)."""
    if state.get("version") != SUMMARY_VERSION:
        return None, True
    summary_reset = _number(state.get("reset"))
    computed = _int(state.get("computed_at"))
    if (summary_reset is None or cache_reset is None
            or abs(summary_reset - cache_reset) > SAME_WINDOW_SECONDS):
        return None, True
    if (_number(state.get("local")) is None or _number(state.get("other")) is None
            or _number(state.get("usd_per_pct")) is None):
        return None, True
    stale = (state.get("rate_label") != RATE_CALIBRATED or computed is None
             or now - computed >= SUMMARY_STALE_SECONDS)
    return state, stale


def _estimated_total(state: Optional[Dict[str, Any]], cache_pct: float,
                     cache_reset: Optional[float], now: float) -> Optional[float]:
    if state is None or cache_reset is None:
        return None
    week = (state.get("claude_estimates") or {}).get("week") \
        if isinstance(state.get("claude_estimates"), dict) else None
    if not isinstance(week, dict):
        return None
    computed = _int(state.get("computed_at"))
    pct = _number(week.get("pct"))
    base = _number(week.get("base"))
    reset = _number(week.get("reset"))
    if computed is None or now - computed >= SUMMARY_STALE_SECONDS or pct is None:
        return None
    if base is None or int(base) != int(cache_pct):
        return None
    if reset is None or abs(reset - cache_reset) > SAME_WINDOW_SECONDS:
        return None
    return pct


def read_claude_week(claude_home: Path, now: float) -> Optional[ClaudeWeek]:
    """The Claude weekly account split; None when the statusline cache has no week value."""
    cache_path = claude_home / CLAUDE_CACHE_NAME
    cache = read_json(cache_path)
    cache_pct = _number((cache or {}).get("week"))
    if cache_pct is None:
        return None
    cache_reset = _number((cache or {}).get("week_reset"))
    summary, split_stale = _week_split(
        read_json(claude_home / CLAUDE_WEEK_SPLIT_NAME) or {}, cache_reset, now)
    total = cache_pct
    total_estimated = _path_mtime(cache_path) == 0 or \
        now - _path_mtime(cache_path) >= SUMMARY_STALE_SECONDS
    if cache_reset is not None and cache_reset <= now:
        # An expired window is already reset: never show yesterday's percentage as current.
        total, cache_reset, total_estimated = 0.0, None, True
        summary, split_stale = None, True
    else:
        estimate = _estimated_total(summary, cache_pct, cache_reset, now)
        if estimate is not None:
            total, total_estimated = estimate, True
    if summary is not None:
        local = _number(summary.get("local"))
        other = _number(summary.get("other"))
        rate = _number(summary.get("usd_per_pct"))
        summary_reset = _number(summary.get("reset"))
        window_start = (summary_reset if summary_reset is not None
                        else cache_reset or now) - WEEK_SECONDS
        return ClaudeWeek(
            window_start=window_start, total_pct=total,
            this_machine_pct=local, other_pct=other,
            resets_at=cache_reset, usd_per_pct=rate,
            total_estimated=total_estimated, split_estimated=split_stale,
            source="statusline_week_split")
    return ClaudeWeek(
        window_start=(cache_reset if cache_reset is not None else now) - WEEK_SECONDS,
        total_pct=total, this_machine_pct=None, other_pct=None,
        resets_at=cache_reset, usd_per_pct=None,
        total_estimated=total_estimated, split_estimated=True,
        source="statusline_cache")


def claude_pct(usd: Optional[float], week: Optional[ClaudeWeek]) -> Optional[float]:
    """Statusline ``session_totals``: group USD divided by USD per 1%."""
    if usd is None or week is None or not week.usd_per_pct:
        return None
    return usd / week.usd_per_pct


def apply_claude_week(usage: Optional[Usage], week: Optional[ClaudeWeek]) -> Optional[Usage]:
    if usage is None:
        return None
    pct = claude_pct(usage.usd, week)
    if pct is None:
        return dataclasses.replace(usage, week_pct=None, week_pct_estimated=True)
    return dataclasses.replace(usage, week_pct=pct,
                   week_pct_estimated=bool(week and week.split_estimated))
