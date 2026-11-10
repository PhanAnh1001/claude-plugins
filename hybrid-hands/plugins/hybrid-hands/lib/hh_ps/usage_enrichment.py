"""Attach token-price estimates and account-scoped quota samples to a snapshot."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import replace
from typing import Any, Optional

from hand_ext.codex_usage import price_for as codex_price
from hand_ext.go_usage import estimate_cost, price_for as go_price
from usage_pricing import explicit_options, token_price
from account_label import backend_account_label

from .models import Usage, Limit
from .timeutil import to_epoch
from .pricing import hand_usage
from .live_rate import read_live_window
from .week import (read_json, _number, _path_mtime, SUMMARY_STALE_SECONDS,
                   GO_LIVE_STALE_SECONDS, GO_LIVE_ERROR_KEEP_SECONDS, _percent)

GO_BACKENDS = frozenset(("dsh", "opencode"))
WEEK_WINDOWS = frozenset(("tuần", "7d", "week"))


def _label(backend: str, cfg: Any) -> str:
    return (backend_account_label(backend, cfg) or "") if cfg is not None else ""


def _account(usage: Usage, plan: str, snapshot: Any, now: float, five: dict,
             label: str = "") -> Usage:
    windows = {row.window: row.total_pct for row in snapshot.limits
               if row.plan == plan and row.source != "ledger"
               and _percent(row.total_pct) is not None
               and row.resets_at is not None and row.resets_at > now}
    week = next((windows[key] for key in WEEK_WINDOWS if key in windows), None)
    if plan not in five:
        five[plan] = _five_hour(plan, now)
    return replace(usage, account_plan=plan, account_5h_pct=windows.get("5h", five[plan]),
                   account_week_pct=week, account_label=label)


def _claude_five(home: Path, now: float):
    path = home / ".statusline-cache.json"
    cache = read_json(path) or {}
    stamp = _path_mtime(path)
    raw_pct = _number(cache.get("five"))
    pct = raw_pct if raw_pct is not None and 0 <= raw_pct <= 100 else None
    reset = to_epoch(cache.get("five_reset"))
    candidate = ((pct, reset, "claude_5h_cache")
                 if pct is not None and reset is not None and now < reset <= now + 18000
                 and 0 <= now - stamp < SUMMARY_STALE_SECONDS else None)
    live = read_live_window(home, "five_hour", now)
    if live is not None and live.resets_at <= now + 18000 and (candidate is None or live.ts > stamp):
        candidate = (live.pct, live.resets_at, "claude_5h_live")
    return candidate


def _five_hour(plan: str, now: float) -> Optional[float]:
    home = Path(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR")
                                 or os.environ.get("CLAUDE_HOME") or "~/.claude"))
    if plan == "Claude":
        sample = _claude_five(home, now)
        return sample[0] if sample is not None else None
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
    current = Path(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))
    configured = options.get("config_dir") or ("~/.claude" if backend in ("claude-main", "claude-v1")
                                               else "~/.claude-hand" if backend == "claude" else None)
    if (backend in ("claude", "claude-main") or backend.startswith("claude-v")) and configured and Path(os.path.expanduser(str(configured))).resolve() == current.resolve():
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
    # These rows are derived from the current cache/live sample, not durable
    # account facts. Rebuild them on every pass, including invalidation.
    snapshot.limits[:] = [row for row in snapshot.limits
                          if row.source not in ("claude_5h_cache", "claude_5h_live")]
    home = Path(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR")
                                 or os.environ.get("CLAUDE_HOME") or "~/.claude"))
    sample = _claude_five(home, now)
    if sample is not None and not any(r.plan == "Claude" and r.window == "5h" for r in snapshot.limits):
        pct, reset, source = sample
        snapshot.limits.append(Limit("Claude", "5h", None, None, pct, reset, source))
    five["Claude"] = sample[0] if sample is not None else None
    for session in snapshot.sessions:
        provider = session.provider
        plan = ("GPT" if provider == "codex" else "Go" if provider in GO_BACKENDS
                else "Claude" if provider == "claude" else "")
        usage = _row_usage(session, cfg)
        if usage is not None:
            session.usage = _account(usage, plan, snapshot, now, five,
                                     _label("codex", cfg) if provider == "codex" else "")
        for agent in session.subagents:
            usage = _row_usage(agent, cfg, provider)
            if usage is not None:
                agent_plan = "GPT" if agent.provider == "codex" else plan
                agent.usage = _account(usage, agent_plan, snapshot, now, five,
                                       _label("codex", cfg) if agent_plan == "GPT" else "")
    for run in snapshot.iter_runs():
        backend = run.backend
        try:
            options = (cfg.options(backend) if cfg is not None and backend.startswith("claude")
                       else explicit_options(cfg, backend))
        except (ValueError, KeyError):
            # Machine/historical ledgers can reference an account removed from this repo.
            # Keep model pricing, but do not borrow another account's quota source.
            options = None
        if backend == "codex":
            price = codex_price(options, run.model)
            plan = "GPT"
        elif backend in GO_BACKENDS:
            price = go_price(options, run.model)
            plan = "Go"
        else:
            price = token_price(run.model)
            # Without configuration, retain the legacy primary-account label.
            # An explicitly missing/removed account above must remain unknown.
            plan = ("Claude" if cfg is None and backend in ("claude-main", "claude-v1")
                    else _run_plan(backend, options) if options is not None else "")
        usage = run.usage or hand_usage(run.tokens, backend, run.week_limit_usd,
                                        run.week_pct_estimated) or Usage(usd=None)
        tokens = run.tokens or {"input": usage.read + usage.cache_read,
                                "cached_input": usage.cache_read, "output": usage.out}
        usd = (None if backend.startswith("claude") and (usage.cache_write
                       or tokens.get("cache_creation_input_tokens") or tokens.get("cache_creation"))
               else estimate_cost(tokens, price) if run.tokens or any(
                   (usage.read, usage.cache_read, usage.out)) else None)
        week = (usage.week_pct if backend == "codex"
                else _go_run_week_pct(backend, usd, run.week_limit_usd))
        run.usage = _account(replace(usage, usd=usd, usd_estimated=usd is not None,
            week_pct=week, week_pct_estimated=(usage.week_pct_estimated if backend == "codex"
                                            else week is not None)), plan, snapshot, now, five,
            _label(backend, cfg) if options is not None or backend == "codex" else "")
