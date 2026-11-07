"""Attach token-price estimates and account-scoped quota samples to a snapshot."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import replace
from typing import Any, Optional

from hand_ext.codex_usage import price_for as codex_price
from hand_ext.go_usage import estimate_cost, price_for as go_price
from usage_pricing import explicit_options, token_price

from .models import Usage
from .pricing import hand_usage
from .live_rate import read_live_window
from .week import (read_json, _number, _path_mtime, SUMMARY_STALE_SECONDS,
                   GO_LIVE_STALE_SECONDS, GO_LIVE_ERROR_KEEP_SECONDS, _percent)

GO_BACKENDS = frozenset(("dsh", "opencode"))
WEEK_WINDOWS = frozenset(("tuần", "7d", "week"))


def _account(usage: Usage, plan: str, snapshot: Any, now: float, five: dict) -> Usage:
    windows = {row.window: row.total_pct for row in snapshot.limits
               if row.plan == plan and row.source != "ledger"
               and _percent(row.total_pct) is not None
               and row.resets_at is not None and row.resets_at > now}
    week = next((windows[key] for key in WEEK_WINDOWS if key in windows), None)
    if plan not in five:
        five[plan] = _five_hour(plan, now)
    return replace(usage, account_plan=plan, account_5h_pct=windows.get("5h", five[plan]),
                   account_week_pct=week)


def _five_hour(plan: str, now: float) -> Optional[float]:
    home = Path(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR")
                                 or os.environ.get("CLAUDE_HOME") or "~/.claude"))
    if plan == "Claude":
        path = home / ".statusline-cache.json"
        cache = read_json(path) or {}
        stamp = _path_mtime(path)
        pct, reset = _percent(cache.get("five")), _number(cache.get("five_reset"))
        live = read_live_window(home, "five_hour", now)
        if live is not None and live.ts > stamp:
            pct, reset, stamp = _percent(live.pct), live.resets_at, live.ts
        return (pct if reset is not None and reset > now
                and 0 <= now - stamp < SUMMARY_STALE_SECONDS else None)
    if plan == "Go":
        cache = read_json(home / ".statusline-go-usage.json") or {}
        windows = cache.get("windows")
        row = windows.get("rolling") if isinstance(windows, dict) else None
        if not isinstance(row, dict):
            return None
        stamp = _number(cache.get("last_ok_at")) or _number(cache.get("fetched_at"))
        ttl = (GO_LIVE_ERROR_KEEP_SECONDS if cache.get("state") == "error"
               else GO_LIVE_STALE_SECONDS)
        reset = _number(row.get("resets_at"))
        if (cache.get("state") in ("ok", "error") and stamp is not None
                and 0 <= now - stamp < ttl and reset is not None and reset > now):
            return _percent(row.get("percent"))
    return None


def _row_usage(row: Any, cfg: Any = None, provider: str = "") -> Usage:
    usage = row.usage or Usage(usd=None)
    backend = getattr(row, "provider", "") or provider
    # Claude transcripts price each message separately. None may mean an unknown
    # model in a mixed-model transcript, so the last model cannot repair it.
    if backend == "claude":
        return usage
    if row.usage is None or (usage.usd is None and not any(
            (usage.read, usage.cache_read, usage.cache_write, usage.out))):
        return usage
    model = getattr(row, "model", "")
    resolved = (codex_price(explicit_options(cfg, backend), model)
                if backend == "codex" else token_price(model))
    usd = estimate_cost({"input": usage.read + usage.cache_read,
                         "cached_input": usage.cache_read, "output": usage.out}, resolved)
    return replace(usage, usd=usd, usd_estimated=usd is not None)


def _run_plan(backend: str, options: dict) -> str:
    if backend == "codex":
        return "GPT"
    if backend in GO_BACKENDS:
        return "Go"
    if backend == "claude-main":
        return "Claude"
    current = Path(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))
    configured = options.get("config_dir")
    if backend == "claude" and configured and Path(os.path.expanduser(str(configured))).resolve() == current.resolve():
        return "Claude"
    return ""


def _go_run_week_pct(backend: str, usd: Optional[float], limit: Any) -> Optional[float]:
    """Only Go's dollar allowance supports a per-run weekly percentage."""
    if backend not in GO_BACKENDS or usd is None:
        return None
    allowance = _number(limit)
    if allowance is None or allowance <= 0:
        return None
    return usd / allowance * 100


def enrich_snapshot(snapshot: Any, cfg: Any, now: float) -> None:
    """Mutate rows only; no network, ledger writes, or inferred account percentages."""
    five: dict = {}
    for session in snapshot.sessions:
        provider = session.provider
        plan = ("GPT" if provider == "codex" else "Go" if provider in GO_BACKENDS
                else "Claude" if provider == "claude" else "")
        usage = _row_usage(session, cfg)
        if usage is not None:
            session.usage = _account(usage, plan, snapshot, now, five)
        for agent in session.subagents:
            usage = _row_usage(agent, cfg, provider)
            if usage is not None:
                agent_plan = "GPT" if agent.provider == "codex" else plan
                agent.usage = _account(usage, agent_plan, snapshot, now, five)
    for run in snapshot.iter_runs():
        backend = run.backend
        options = explicit_options(cfg, backend)
        if backend == "codex":
            price = codex_price(options, run.model)
            plan = "GPT"
        elif backend in GO_BACKENDS:
            price = go_price(options, run.model)
            plan = "Go"
        else:
            price = token_price(run.model)
            plan = _run_plan(backend, options)
        usage = run.usage or hand_usage(run.tokens, backend, run.week_limit_usd,
                                        run.week_pct_estimated) or Usage(usd=None)
        tokens = run.tokens or {"input": usage.read + usage.cache_read,
                                "cached_input": usage.cache_read, "output": usage.out}
        usd = (None if backend.startswith("claude") and (usage.cache_write
                       or tokens.get("cache_creation_input_tokens") or tokens.get("cache_creation"))
               else estimate_cost(tokens, price) if run.tokens or any(
                   (usage.read, usage.cache_read, usage.out)) else None)
        week = _go_run_week_pct(backend, usd, run.week_limit_usd)
        run.usage = _account(replace(usage, usd=usd, usd_estimated=usd is not None,
            week_pct=week, week_pct_estimated=week is not None), plan, snapshot, now, five)
