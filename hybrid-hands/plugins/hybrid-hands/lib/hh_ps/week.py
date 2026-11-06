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
import functools
import importlib.util
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from hand_ext.constants import GO_USAGE_DEFAULT_PRICE
from hand_ext.go_usage import estimate_cost

from .live_rate import read_live_window
from .models import Usage

DAY_SECONDS = 86400
WEEK_SECONDS = 7 * DAY_SECONDS
SAME_WINDOW_SECONDS = 3600
SUMMARY_STALE_SECONDS = 1800
GO_LIVE_STALE_SECONDS = 900
GO_LIVE_ERROR_KEEP_SECONDS = 21600
SUMMARY_VERSION = 2
RATE_CALIBRATED = "calib"
# statusline labels whose USD per 1 % is trusted: calibrated, or pinned by the user.
TRUSTED_RATE_LABELS = (RATE_CALIBRATED, "pin")
PERCENT = 100.0
GO_MODEL_MARKER = "deepseek"
GO_WEEK_KEY = "7d"
GO_USAGE_LOG_NAME = "go_usage.jsonl"
GO_SUMMARY_NAME = "go_usage_summary.json"
GO_LIVE_CACHE_NAME = ".statusline-go-usage.json"
CLAUDE_CACHE_NAME = ".statusline-cache.json"
CLAUDE_WEEK_SPLIT_NAME = ".statusline-week-split.json"
# Statusline's per-message USD ledger; only version 3 stores USD (v1 stores relative units).
CLAUDE_LOCAL_USAGE_NAME = ".statusline-local-usage.json"
LOCAL_LEDGER_VERSION = 3
WEEK_SPLIT_SOURCE = "statusline_week_split"
LIVE_WINDOW = "seven_day"
LIVE_SOURCE = "rate_limit_event"
WEEK_SPLIT_SUFFIX = "+week_split"
EXTRAPOLATED_SUFFIX = "+extrapolated"
# Test override: path to statusline's usage_ledger.py; missing means "no fresh source".
STATUSLINE_LEDGER_ENV = "HH_PS_STATUSLINE_LEDGER"
STATUSLINE_PLUGIN_KEY = "statusline@statusline-local"
STATUSLINE_PLUGIN_PREFIX = "statusline@"
STATUSLINE_LEDGER_FILE = "usage_ledger.py"
INSTALLED_PLUGINS_RELPATH = Path("plugins") / "installed_plugins.json"
REPO_STATUSLINE_LEDGER = (Path("statusline") / "plugins" / "statusline"
                          / "scripts" / STATUSLINE_LEDGER_FILE)
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
    stale = (state.get("rate_label") not in TRUSTED_RATE_LABELS or computed is None
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


def _ledger_row_usd(row: Any, since: float, until: float) -> float:
    """USD of one ledger row inside [since, until], else 0."""
    if not isinstance(row, list) or len(row) < 2:
        return 0.0
    ts, usd = _number(row[0]), _number(row[1])
    if ts is None or usd is None or not since <= ts <= until:
        return 0.0
    return usd


def _ledger_usd_since(claude_home: Path, since: float, until: float) -> Optional[float]:
    """This machine's USD after ``since`` from the statusline ledger; None when unusable."""
    ledger = read_json(claude_home / CLAUDE_LOCAL_USAGE_NAME)
    if ledger is None or ledger.get("version") != LOCAL_LEDGER_VERSION:
        return None
    messages = ledger.get("messages")
    if not isinstance(messages, dict):
        return None
    return sum(_ledger_row_usd(row, since, until) for row in messages.values())


def _installed_ledger(claude_home: Path) -> Optional[Path]:
    """usage_ledger.py of the installed statusline plugin, as its shim finds it."""
    document = read_json(claude_home / INSTALLED_PLUGINS_RELPATH)
    plugins = (document or {}).get("plugins")
    if not isinstance(plugins, dict):
        return None
    keys = [STATUSLINE_PLUGIN_KEY]
    keys.extend(name for name in plugins if name.startswith(STATUSLINE_PLUGIN_PREFIX))
    for key in keys:
        entries = plugins.get(key)
        if not isinstance(entries, list) or not entries:
            continue
        entry = entries[0]
        install_path = entry.get("installPath") if isinstance(entry, dict) else None
        if not isinstance(install_path, str) or not install_path:
            continue
        candidate = Path(install_path) / "scripts" / STATUSLINE_LEDGER_FILE
        if candidate.is_file():
            return candidate
    return None


def _repo_ledger() -> Optional[Path]:
    """usage_ledger.py in the statusline/ folder beside hybrid-hands, when run from the repo."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / REPO_STATUSLINE_LEDGER
        if candidate.is_file():
            return candidate
    return None


def _locate_usage_ledger(claude_home: Path) -> Optional[Path]:
    override = os.environ.get(STATUSLINE_LEDGER_ENV)
    if override:
        # An explicit path (the tests point it at the repo) never falls through to ~/.claude.
        path = Path(os.path.expanduser(override))
        return path if path.is_file() else None
    return _installed_ledger(claude_home) or _repo_ledger()


@functools.lru_cache(maxsize=4)
def _ledger_module(path_text: str, mtime_ns: int) -> Any:
    """Load statusline's usage_ledger.py by path, without touching sys.path."""
    spec = importlib.util.spec_from_file_location("hh_ps_statusline_usage_ledger", path_text)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path_text}")
    module = importlib.util.module_from_spec(spec)
    # Python 3.9 dataclasses resolve their module through sys.modules; keep it registered.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _window_usd(module: Any, claude_home: Path, since: float, until: float) -> float:
    """USD of this home's messages in [since, until], using statusline's own price table."""
    messages = module.window_messages([claude_home], since, until)
    return sum(sum(module.model_usd(message.model, message.tokens).values())
               for message in messages.values())


def _fresh_ledger_usd(claude_home: Path, since: float, until: float) -> Optional[float]:
    """USD from transcripts through statusline's usage_ledger.py; None when it is unusable."""
    try:
        path = _locate_usage_ledger(claude_home)
        if path is None:
            return None
        module = _ledger_module(str(path), path.stat().st_mtime_ns)
        return _window_usd(module, claude_home, since, until)
    except Exception:
        # Fail open: a missing/broken statusline plugin must leave the panel on the old source.
        return None


def _usd_since(claude_home: Path, since: float, until: float) -> Optional[float]:
    """This machine's USD after ``since``: fresh transcripts first, then the on-disk ledger."""
    usd = _fresh_ledger_usd(claude_home, since, until)
    if usd is None:
        usd = _ledger_usd_since(claude_home, since, until)
    return usd


def _extrapolate_week(claude_home: Path, anchor_ts: float, anchor_pct: float,
                      summary: Dict[str, Any], total: float,
                      now: float) -> Optional[tuple[float, Optional[float]]]:
    """(total, this machine) grown by USD after ``anchor_ts``, or None to keep the old number."""
    rate = _number(summary.get("usd_per_pct"))
    if not rate:
        return None
    usd = _usd_since(claude_home, anchor_ts, now)
    if usd is None:
        return None
    # Anchor at anchor_pct: an existing estimate already includes post-anchor USD, so never add
    # fresh USD on top of ``total`` (only keep it as a floor).
    grown = min(max(anchor_pct + usd / rate, total, anchor_pct), PERCENT)
    local = _number(summary.get("local"))
    return grown, (local + usd / rate if local is not None else None)


def _live_split(claude_home: Path, cache_ts: float, summary: Dict[str, Any],
                total: float, now: float) -> tuple[Optional[float], Optional[float]]:
    """This machine/other split for a live sample: grow ``local`` by post-cache USD."""
    local = _number(summary.get("local"))
    rate = _number(summary.get("usd_per_pct"))
    if local is not None and rate and cache_ts > 0:
        usd = _usd_since(claude_home, cache_ts, now)
        if usd is not None:
            local += usd / rate
    other = _number(summary.get("other"))
    if local is not None:
        other = max(total - local, 0.0)
    return local, other


def read_claude_week(claude_home: Path, now: float) -> Optional[ClaudeWeek]:
    """The Claude weekly account split; uses the live wrapper sample when it is the newest."""
    cache_path = claude_home / CLAUDE_CACHE_NAME
    cache = read_json(cache_path)
    cache_pct = _number((cache or {}).get("week"))
    cache_ts = _path_mtime(cache_path)
    live = read_live_window(claude_home, LIVE_WINDOW, now)
    use_live = live is not None and (cache_ts == 0 or live.ts > cache_ts)
    if cache_pct is None and not use_live:
        return None
    cache_reset = _number((cache or {}).get("week_reset"))
    if use_live:
        anchor_pct, anchor_ts, reset = live.pct, live.ts, live.resets_at
    else:
        anchor_pct, anchor_ts, reset = cache_pct, cache_ts, cache_reset
    summary, split_stale = _week_split(
        read_json(claude_home / CLAUDE_WEEK_SPLIT_NAME) or {}, reset, now)
    total = anchor_pct
    total_estimated = anchor_ts == 0 or now - anchor_ts >= SUMMARY_STALE_SECONDS
    extrapolated: Optional[tuple[float, Optional[float]]] = None
    if reset is not None and reset <= now:
        # An expired window is already reset: never show yesterday's percentage as current.
        total, reset, total_estimated = 0.0, None, True
        summary, split_stale = None, True
    else:
        if not use_live or total_estimated:
            estimate = _estimated_total(summary, anchor_pct, reset, now)
            if estimate is not None:
                total, total_estimated = estimate, True
        if total_estimated and summary is not None:
            extrapolated = _extrapolate_week(claude_home, anchor_ts, anchor_pct,
                                             summary, total, now)
            if extrapolated is not None:
                total = extrapolated[0]
    if summary is not None:
        local = _number(summary.get("local"))
        other = _number(summary.get("other"))
        rate = _number(summary.get("usd_per_pct"))
        summary_reset = _number(summary.get("reset"))
        window_start = (summary_reset if summary_reset is not None
                        else reset or now) - WEEK_SECONDS
        if use_live:
            local, other = _live_split(claude_home, cache_ts, summary, total, now)
            source = LIVE_SOURCE + WEEK_SPLIT_SUFFIX
            split_estimated = True
        else:
            if extrapolated is not None:
                local = extrapolated[1]
            source = WEEK_SPLIT_SOURCE
            split_estimated = split_stale
        return ClaudeWeek(
            window_start=window_start, total_pct=total,
            this_machine_pct=local, other_pct=other,
            resets_at=reset, usd_per_pct=rate,
            total_estimated=total_estimated, split_estimated=split_estimated,
            source=source + (EXTRAPOLATED_SUFFIX if extrapolated else ""))
    if use_live:
        return ClaudeWeek(
            window_start=(reset if reset is not None else now) - WEEK_SECONDS,
            total_pct=total, this_machine_pct=None, other_pct=None,
            resets_at=reset, usd_per_pct=None,
            total_estimated=total_estimated, split_estimated=True,
            source=LIVE_SOURCE + (EXTRAPOLATED_SUFFIX if extrapolated else ""))
    return ClaudeWeek(
        window_start=(reset if reset is not None else now) - WEEK_SECONDS,
        total_pct=total, this_machine_pct=None, other_pct=None,
        resets_at=reset, usd_per_pct=None,
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
