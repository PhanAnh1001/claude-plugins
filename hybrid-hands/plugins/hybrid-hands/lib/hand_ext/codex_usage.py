"""Codex usage ledger: one JSON line per finished codex turn.

The ChatGPT plan can expose 5-hour and weekly windows, identified by window_minutes. Each line
keeps those windows separately (never only the fullest one) so `hh-ps`/statusline can show
both. Token costs are estimates from `backends.codex.price_per_mtok`; without a complete
price the line has `cost_usd: null` and `cost_source: "unknown"` instead of inventing one.

Schema (schema = 1):
  run_id, ended, model, effort,
  tokens {input, cached_input, output},
  cost_usd (number|null), cost_source ("estimated"|"unknown"),
  codex_home (basename only, e.g. ".codex-hand"),
  windows {"5h": {"used_percent", "resets_at"} | null,
           "7d": {"used_percent", "resets_at"} | null}

The file lives beside the Go ledger: `~/.hybrid-hands/codex_usage.jsonl`, or
`$HYBRID_HANDS_STATE_DIR/codex_usage.jsonl` when that variable is set (tests).
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from usage_pricing import token_price, explicit_options

from .backends import codex
from .constants import CODEX_PRICE_KEY, CODEX_USAGE_LEDGER_NAME
from .go_usage import COST_ESTIMATED, COST_UNKNOWN, _number, estimate_cost
from .locked_json import locked

SCHEMA_VERSION = 1
MODEL_UNKNOWN = "unknown"
TOKEN_KEYS = ("input", "cached_input", "output")
WINDOW_KEYS = ("5h", "7d")
USD_DECIMALS = 6


def ledger_path(cfg: Any) -> Path:
    return Path(cfg.machine_state_dir) / CODEX_USAGE_LEDGER_NAME


def price_for(options: Optional[dict], model: str = "gpt-6.1-sol") -> Optional[Dict[str, float]]:
    """`backends.codex.price_per_mtok` = {input, cached, output} USD/1M, or None."""
    if CODEX_PRICE_KEY not in (options or {}):
        return token_price(model)
    raw = (options or {}).get(CODEX_PRICE_KEY)
    if not isinstance(raw, dict):
        return None
    cached = raw.get("cached", raw.get("cached_input"))
    price: Dict[str, float] = {}
    for key, value in (("input", raw.get("input")), ("cached_input", cached),
                       ("output", raw.get("output"))):
        number = _number(value)
        if number is None:
            return None
        price[key] = number
    return price


def _token(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _reset(value: Any) -> Optional[str]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return dt.datetime.fromtimestamp(float(value), dt.timezone.utc).isoformat(
            timespec="seconds")
    text = str(value or "").strip()
    return text or None


def _window(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    used = _number(raw.get("used_percent"))
    if used is None:
        return None
    return {"used_percent": used, "resets_at": _reset(raw.get("resets_at"))}


def normalize_windows(raw: Any) -> Dict[str, Optional[Dict[str, Any]]]:
    windows = raw if isinstance(raw, dict) else {}
    return {key: _window(windows.get(key)) for key in WINDOW_KEYS}


def build_record(run_id: str, ended: str, model: str, effort: str, tokens: Dict[str, Any],
                 cost_usd: Optional[float], cost_source: str, codex_home: str,
                 windows: Any) -> Dict[str, Any]:
    tokens = tokens if isinstance(tokens, dict) else {}
    cost = _number(cost_usd)
    source = COST_ESTIMATED if cost is not None and cost_source == COST_ESTIMATED \
        else COST_UNKNOWN
    return {
        "schema": SCHEMA_VERSION,
        "run_id": str(run_id),
        "ended": str(ended),
        "model": str(model or MODEL_UNKNOWN),
        "effort": str(effort or MODEL_UNKNOWN),
        "tokens": {key: _token(tokens.get(key)) for key in TOKEN_KEYS},
        "cost_usd": round(cost, USD_DECIMALS) if cost is not None else None,
        "cost_source": source,
        "codex_home": Path(os.path.expanduser(str(codex_home or ""))).name or MODEL_UNKNOWN,
        "windows": normalize_windows(windows),
    }


def record_run(cfg: Any, entry: Dict[str, Any], spec: Any,
               windows: Any = None) -> Dict[str, Any]:
    """Append one codex turn; only file errors escape (the caller warns and keeps going)."""
    tokens = entry.get("tokens")
    tokens = tokens if isinstance(tokens, dict) else {}
    price = price_for(explicit_options(cfg, "codex"), str(entry.get("model") or ""))
    cost = estimate_cost(tokens, price)
    source = COST_ESTIMATED if cost is not None else COST_UNKNOWN
    record = build_record(str(entry.get("run_id") or ""), str(entry.get("ended") or ""),
                          str(entry.get("model") or ""), str(entry.get("effort") or ""),
                          tokens, cost, source, str(codex.home_dir(spec.options)), windows)
    path = ledger_path(cfg)
    with locked(path):
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
