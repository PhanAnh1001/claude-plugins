"""Main-session groups with their Claude and OpenCode Go usage (Go from hand-ext's run ledger).

A group is one main Claude session (its subagents share its session id) plus every claude side
session below it. Finished runs come from go_usage.jsonl (cost_usd), runs still going from the
run registry (tokens priced with the default Go price table). The Go week window comes from the
live usage cache, the weekly USD limit from go_usage_summary.json.

The default price table and the cost formula are ported from hybrid-hands
plugins/hybrid-hands/lib/hand_ext/go_usage.py (estimate_cost) and constants.py
(GO_USAGE_DEFAULT_PRICE); no hybrid-hands code is imported.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DAY_SECONDS = 86400
GO_WEEK_SECONDS = 7 * DAY_SECONDS
STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
DEFAULT_STATE_DIR = Path.home() / ".hybrid-hands"
GO_LIVE_CACHE_NAME = ".statusline-go-usage.json"
GO_SUMMARY_NAME = "go_usage_summary.json"
GO_USAGE_LOG_NAME = "go_usage.jsonl"
RUNS_SUBDIR = "runs"
RUN_STATUS_RUNNING = "running"
GO_MODEL_MARKER = "deepseek"
GO_WEEK_KEY = "7d"
TOKENS_PER_MTOK = 1_000_000
PERCENT = 100.0
USD_DECIMALS = 4
PCT_DECIMALS = 2
# Peak Go prices, USD per 1M tokens (https://opencode.ai/docs/go, read 2026-11-04 by hybrid-hands).
# Peak keeps the estimate an upper bound; the OpenCode Console stays the authoritative meter.
GO_DEFAULT_PRICE = {"input": 0.30, "cached_input": 0.006, "output": 1.20}


@dataclass(frozen=True)
class GoRun:
    run_id: str
    usd: float
    parent: Optional[str]
    cwd: str


@dataclass(frozen=True)
class GoWeek:
    window_start: float
    limit_usd: float
    runs: list[GoRun]


def state_dir() -> Path:
    return Path(os.environ.get(STATE_DIR_ENV) or DEFAULT_STATE_DIR)


def read_json(path: Path) -> Optional[dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse_iso(value: object) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def go_week_start(home: Path) -> Optional[float]:
    """Start of the Go week window: the live cache's weekly reset minus 7 days."""
    cache = read_json(home / GO_LIVE_CACHE_NAME) or {}
    weekly = (cache.get("windows") or {}).get("weekly") if isinstance(cache.get("windows"), dict) else None
    reset = number(weekly.get("resets_at")) if isinstance(weekly, dict) else None
    return reset - GO_WEEK_SECONDS if reset else None


def go_week_limit(state: Path) -> Optional[float]:
    summary = read_json(state / GO_SUMMARY_NAME) or {}
    models = summary.get("models")
    if not isinstance(models, dict):
        return None
    for name, windows in models.items():
        if GO_MODEL_MARKER in str(name).lower() and isinstance(windows, dict):
            week = windows.get(GO_WEEK_KEY)
            limit = number(week.get("limit_usd")) if isinstance(week, dict) else None
            if limit and limit > 0:
                return limit
    return None


def _tokens(value: object) -> float:
    count = number(value)
    return max(0.0, count) if count is not None else 0.0


def estimate_cost(tokens: object) -> float:
    """USD for a run's tokens: uncached input + cached input + output, each at its own price."""
    if not isinstance(tokens, dict):
        return 0.0
    total_input, cached = _tokens(tokens.get("input")), _tokens(tokens.get("cached_input"))
    uncached = max(0.0, total_input - cached)
    cost = (uncached * GO_DEFAULT_PRICE["input"] + cached * GO_DEFAULT_PRICE["cached_input"]
            + _tokens(tokens.get("output")) * GO_DEFAULT_PRICE["output"]) / TOKENS_PER_MTOK
    return round(cost, USD_DECIMALS + 2)


def load_registry(state: Path) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    try:
        paths = sorted((state / RUNS_SUBDIR).glob("*.json"))
    except OSError:
        return registry
    for path in paths:
        record = read_json(path)
        if record is not None:
            registry[str(record.get("run_id") or path.stem)] = record
    return registry


def _parent(record: Optional[dict]) -> Optional[str]:
    parent = (record or {}).get("parent_session")
    return parent if isinstance(parent, str) and parent else None


def _cwd(record: Optional[dict]) -> str:
    cwd = (record or {}).get("cwd")
    return cwd if isinstance(cwd, str) else ""


def finished_runs(state: Path, start: float, registry: dict[str, dict]) -> tuple[list[GoRun], set[str]]:
    """Runs in go_usage.jsonl ended inside the window, and the ids of every logged run."""
    runs: list[GoRun] = []
    logged: set[str] = set()
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
        ended, usd = parse_iso(record.get("ended")), number(record.get("cost_usd"))
        if ended is None or ended < start or usd is None:
            continue
        entry = registry.get(run_id)
        runs.append(GoRun(run_id, usd, _parent(entry), _cwd(entry)))
    return runs, logged


def running_runs(registry: dict[str, dict], logged: set[str]) -> list[GoRun]:
    return [GoRun(run_id, estimate_cost(record.get("tokens")), _parent(record), _cwd(record))
            for run_id, record in registry.items()
            if record.get("status") == RUN_STATUS_RUNNING and run_id not in logged]


def load_go_week(home: Path, state: Path) -> Optional[GoWeek]:
    """The Go week window, its USD limit and its runs; None when the window or limit is unknown."""
    start, limit = go_week_start(home), go_week_limit(state)
    if start is None or limit is None:
        return None
    registry = load_registry(state)
    finished, logged = finished_runs(state, start, registry)
    return GoWeek(start, limit, finished + running_runs(registry, logged))


def group_total(sid: str, own: dict[str, float], children: dict[str, set[str]]) -> float:
    """USD of sid plus every descendant side session (cycle-safe)."""
    seen, stack, total = {sid}, [sid], 0.0
    while stack:
        current = stack.pop()
        total += own.get(current, 0.0)
        for child in children.get(current, ()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return total


def tree_members(root: str, children: dict[str, set[str]]) -> list[str]:
    """root followed by every descendant side session, sorted (cycle-safe)."""
    seen, stack = {root}, [root]
    while stack:
        for child in children.get(stack.pop(), ()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return [root, *sorted(seen - {root})]


def go_own(week: Optional[GoWeek]) -> dict[str, float]:
    own: dict[str, float] = {}
    for run in (week.runs if week else []):
        if run.parent:
            own[run.parent] = own.get(run.parent, 0.0) + run.usd
    return own


def build_groups(claude_own: dict[str, float], children: dict[str, set[str]],
                 usd_per_pct: float, week: Optional[GoWeek],
                 names: dict[str, tuple[str, str]]) -> list[dict]:
    """One entry per main session (a root of the side-session tree) with Claude and Go usage.

    Sorted by Claude % descending. go_usd/go_pct are null when the Go week is unknown.
    """
    go = go_own(week)
    child_ids = set().union(*children.values()) if children else set()
    sids = set(claude_own) | set(go) | set(children) | child_ids
    groups = []
    for root in sorted(sid for sid in sids if sid not in child_ids):
        members = tree_members(root, children)
        claude_usd = sum(claude_own.get(sid, 0.0) for sid in members)
        go_usd = sum(go.get(sid, 0.0) for sid in members)
        name, alias = names.get(root, ("", ""))
        groups.append({
            "root": root, "name": name, "alias": alias, "members": members,
            "claude_usd": round(claude_usd, USD_DECIMALS),
            "claude_pct": round(claude_usd / usd_per_pct, PCT_DECIMALS),
            "go_usd": round(go_usd, USD_DECIMALS) if week else None,
            "go_pct": round(go_usd / week.limit_usd * PERCENT, PCT_DECIMALS) if week else None,
        })
    groups.sort(key=lambda g: (-g["claude_pct"], g["root"]))
    return groups


def go_week_summary(week: GoWeek) -> dict:
    return {"window_start": int(week.window_start), "limit_usd": week.limit_usd}
