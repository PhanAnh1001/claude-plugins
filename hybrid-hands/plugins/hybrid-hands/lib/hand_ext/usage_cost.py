"""Token-cost helpers shared by the Codex ledger and hh-ps (USD~ estimates, never bills).

Prices come only from config/model-prices.json through `usage_pricing.token_price`; an
unknown model has no price and the cost stays unknown (no family fallback).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from usage_pricing import token_price

COST_EXACT = "exact"
COST_ESTIMATED = "estimated"
COST_UNKNOWN = "unknown"
TOKENS_PER_MTOK = 1_000_000
TOKEN_KEYS = ("input", "cached_input", "output")
USD_DECIMALS = 6


def number(value: Any) -> Optional[float]:
    """Finite non-negative float, or None; bool and strings are not accepted."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) and result >= 0 else None


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def price_for(options: Optional[dict] = None, model: str = "") -> Optional[Dict[str, float]]:
    """Canonical price of `model`; `options` is accepted for caller compatibility only."""
    del options  # backend price overrides live in codex_usage.price_for
    return token_price(model) if model else None


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


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Object lines of a JSONL ledger; a torn final line is skipped, not fatal."""
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
            continue
        if isinstance(item, dict):
            records.append(item)
    return records
