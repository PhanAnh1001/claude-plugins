"""Machine-wide OpenCode Go usage ledger and rolling 5h/7d/30d summary.

The Go plan counts usage in USD per model, not per repository: every hand run that goes
through `dsh` appends one JSON line to `~/.hybrid-hands/go_usage.jsonl`
(overridable through `ext_hand.go_usage.ledger` or `HYBRID_HANDS_STATE_DIR`). The summary
beside it is recomputed under the ledger lock after each run and by `hand-ext usage`.
Lines left by the removed `opencode` backend (before 0.19.0) still count.

OpenCode reports the authoritative amount as `opencode.allowance` on API responses, but the
installed CLI keeps neither that field nor a usable cost: dsh drops pi-ai's cost metadata
(console API docs, read 2026-11-04). So current runs are estimates from tokens and the configured token price;
`exact` is used when a backend ever surfaces `go_allowance_usd`.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from usage_pricing import token_price, explicit_options

from .config import ExtConfig
from .constants import (
    GO_PRICE_KEY, GO_USAGE_WINDOW_SHARES,
)
from .locked_json import locked, write_atomic

COST_EXACT = "exact"
COST_ESTIMATED = "estimated"
COST_UNKNOWN = "unknown"
MODEL_UNKNOWN = "unknown"
GO_PROVIDER_PREFIX = "opencode-go/"
DEEPSEEK_MARKER = "deepseek"
SCHEMA_VERSION = 1
TOKENS_PER_MTOK = 1_000_000
TOKEN_KEYS = ("input", "cached_input", "output")
PERCENT_DECIMALS = 2
USD_DECIMALS = 6
WINDOW_KEYS = tuple(key for key, _, _ in GO_USAGE_WINDOW_SHARES)


def normalize_model(raw: Any) -> str:
    model = str(raw or "").strip()
    if model.startswith(GO_PROVIDER_PREFIX):
        model = model[len(GO_PROVIDER_PREFIX):]
    return model or MODEL_UNKNOWN


def _number(value: Any) -> Optional[float]:
    """Finite non-negative float, or None; bool and strings are not accepted."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def price_for(options: Optional[dict], model: str = "deepseek-v4.1-flash") -> Optional[Dict[str, float]]:
    """`backends.<name>.go_price_per_mtok`, defaulting to the docs' peak Go prices."""
    options = options or {}
    raw = options.get(GO_PRICE_KEY)
    if raw is None and GO_PRICE_KEY not in options:
        return token_price(model)
    if not isinstance(raw, dict):
        return None
    price: Dict[str, float] = {}
    for key in TOKEN_KEYS:
        value = _number(raw.get(key))
        if value is None:
            return None
        price[key] = value
    return price


def estimate_cost(tokens: Dict[str, Any], price: Optional[Dict[str, float]]) -> Optional[float]:
    """USD for one turn: uncached input + cached input + output, each at its own price."""
    if not price or any(key not in price for key in TOKEN_KEYS):
        return None
    total_input = _token_count(tokens.get("input"))
    cached = _token_count(tokens.get("cached_input"))
    uncached = max(0, total_input - cached)
    output = _token_count(tokens.get("output"))
    cost = (uncached * price["input"] + cached * price["cached_input"]
            + output * price["output"]) / TOKENS_PER_MTOK
    return round(cost, USD_DECIMALS)


def resolve_cost(tokens: Dict[str, Any], exact_usd: Any,
                 price: Optional[Dict[str, float]]) -> Tuple[Optional[float], str]:
    exact = _number(exact_usd)
    if exact is not None:
        return round(exact, USD_DECIMALS), COST_EXACT
    estimated = estimate_cost(tokens, price)
    if estimated is None:
        return None, COST_UNKNOWN
    return estimated, COST_ESTIMATED


def build_record(run_id: str, ended: str, backend: str, model: str,
                 tokens: Dict[str, Any], cost_usd: Optional[float], cost_source: str,
                 cwd: Optional[str]) -> Dict[str, Any]:
    """One ledger line; only the cwd basename is kept, never an absolute path."""
    cost = _number(cost_usd)
    source = cost_source if cost is not None and cost_source in (COST_EXACT, COST_ESTIMATED) \
        else COST_UNKNOWN
    return {
        "run_id": str(run_id),
        "ended": str(ended),
        "backend": str(backend),
        "model": normalize_model(model),
        "tokens": {key: _token_count(tokens.get(key)) for key in TOKEN_KEYS},
        "cost_usd": cost,
        "cost_source": source,
        "cwd_basename": Path(str(cwd or "")).name,
    }


def _epoch(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
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


def _empty_windows() -> Dict[str, Dict[str, Any]]:
    return {key: {"used": 0.0, "estimated": False} for key in WINDOW_KEYS}


def summarize(records: List[Dict[str, Any]], monthly_limit_usd: float,
              now: Optional[float] = None) -> Dict[str, Any]:
    """Sum costs per model into sliding windows ending at `now` (epoch seconds)."""
    moment = time.time() if now is None else float(now)
    limit = float(monthly_limit_usd)
    buckets: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for record in records:
        ended = _epoch(record.get("ended"))
        if ended is None:
            continue
        model = normalize_model(record.get("model"))
        windows = buckets.setdefault(model, _empty_windows())
        cost = _number(record.get("cost_usd"))
        exact = record.get("cost_source") == COST_EXACT and cost is not None
        for key, seconds, _ in GO_USAGE_WINDOW_SHARES:
            if ended < moment - seconds:
                continue
            windows[key]["used"] += cost or 0.0
            if not exact:
                windows[key]["estimated"] = True
    models: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for model in sorted(buckets):
        models[model] = {}
        for key, _, share in GO_USAGE_WINDOW_SHARES:
            used = round(buckets[model][key]["used"], USD_DECIMALS)
            window_limit = round(limit * share, 2)
            percent = round(used / window_limit * 100, PERCENT_DECIMALS) \
                if window_limit > 0 else 0.0
            models[model][key] = {
                "used_usd": used,
                "limit_usd": window_limit,
                "percent": percent,
                "estimated": buckets[model][key]["estimated"],
            }
    return {
        "schema": SCHEMA_VERSION,
        "updated_at": int(moment),
        "monthly_limit_usd": round(limit, 2),
        "models": models,
    }


def primary_model(summary: Optional[Dict[str, Any]]) -> Optional[str]:
    """DeepSeek model key of a summary, or None when it has no such model."""
    models = (summary or {}).get("models")
    if not isinstance(models, dict):
        return None
    for name in models:
        if DEEPSEEK_MARKER in str(name).lower():
            return str(name)
    return None


def summary_line(summary: Optional[Dict[str, Any]]) -> Optional[str]:
    """`hạn mức: ~x% 5h, ~y% tuần (ước tính)` for the run output, or None without data."""
    model = primary_model(summary)
    windows = (summary or {}).get("models", {}).get(model, {}) if model else {}
    five, week = windows.get("5h") or {}, windows.get("7d") or {}
    if "percent" not in five or "percent" not in week:
        return None
    estimated = bool(five.get("estimated") or week.get("estimated"))
    mark = "~" if estimated else ""
    suffix = " (ước tính)" if estimated else ""
    return (f"hạn mức: {mark}{float(five['percent']):.0f}% 5h, "
            f"{mark}{float(week['percent']):.0f}% tuần{suffix}")


def _read_records_unlocked(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue  # a torn final line must not break usage reporting
        if isinstance(item, dict):
            records.append(item)
    return records


def write_summary(path: Path, summary: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, summary)


def read_summary(path: Path) -> Optional[Dict[str, Any]]:
    """Parsed summary, or None when absent/corrupt (the status line prints nothing)."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def refresh(cfg: ExtConfig, now: Optional[float] = None) -> Dict[str, Any]:
    """Recompute the summary from the ledger under its lock, then write it atomically."""
    with locked(cfg.go_usage_ledger):
        summary = summarize(_read_records_unlocked(cfg.go_usage_ledger),
                            cfg.go_monthly_limit_usd, now)
        write_summary(cfg.go_usage_summary, summary)
    return summary


def record_run(cfg: ExtConfig, entry: Dict[str, Any], exact_usd: Any = None,
               now: Optional[float] = None) -> Dict[str, Any]:
    """Append one Go turn and refresh the summary, serialised on the ledger lock."""
    backend = str(entry.get("backend") or "")
    tokens = entry.get("tokens") or {}
    cost, source = resolve_cost(tokens, exact_usd, price_for(explicit_options(cfg, backend), str(entry.get("model") or "")))
    record = build_record(str(entry.get("run_id") or ""), str(entry.get("ended") or ""),
                          backend, str(entry.get("model") or ""), tokens, cost, source,
                          str(entry.get("cwd") or ""))
    with locked(cfg.go_usage_ledger):
        with cfg.go_usage_ledger.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary = summarize(_read_records_unlocked(cfg.go_usage_ledger),
                            cfg.go_monthly_limit_usd, now)
        write_summary(cfg.go_usage_summary, summary)
    return summary


def format_text(summary: Optional[Dict[str, Any]]) -> str:
    """Human table for `hand-ext usage`; Console is called out as the source of truth."""
    lines = ["Go (DeepSeek V4.1 Flash, tài khoản dùng chung):", "",
             "| model | cửa sổ | đã dùng (USD) | hạn mức (USD) | % | nguồn |",
             "|---|---|---|---|---|---|"]
    raw_models = (summary or {}).get("models")
    models = raw_models if isinstance(raw_models, dict) else {}
    for model in sorted(models):
        windows = models[model] if isinstance(models[model], dict) else {}
        for key, _, _ in GO_USAGE_WINDOW_SHARES:
            window = windows.get(key) if isinstance(windows.get(key), dict) else {}
            source = "ước tính" if window.get("estimated") else "chính xác"
            percent = _number(window.get("percent")) or 0.0
            lines.append(f"| {model} | {key} | {window.get('used_usd', 0)} | "
                         f"{window.get('limit_usd', 0)} | {percent:g}% | {source} |")
    if not models:
        lines.append("| (chưa có lượt Go nào) | - | 0 | - | 0% | - |")
    lines += ["", "Cửa sổ của Go có thể không trượt "
                  "(OpenCode chưa công bố mốc reset), "
                  "nên số ở đây là ước tính; OpenCode Console là nguồn chuẩn."]
    return "\n".join(lines)
