"""Model prices and USD estimates for the shared usage library.

Ported from statusline plugins/statusline/scripts/usage_ledger.py (the USD/MTok
price table, family fallback, cache multipliers and the usage formula).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


from .models import Usage
from usage_pricing import model_price, load_prices

PER_TOKENS = 1_000_000
SYNTHETIC_MODEL = "<synthetic>"
# Hand token buckets in a `{input, cached_input, output}` price row (USD/MTok).
TOKEN_KEYS = ("input", "cached_input", "output")
# Same rounding the hand-ext ledgers used, so historical rows stay comparable.
USD_DECIMALS = 6


@dataclass(frozen=True)
class ModelPrice:
    input: float   # USD per million input tokens
    output: float  # USD per million output tokens
    cached: Optional[float] = None
    cache_write_5m: Optional[float] = None
    cache_write_1h: Optional[float] = None


# The public two-field constructor remains compatible with older callers.
def price_for(model: str) -> Optional[ModelPrice]:
    row = model_price(model)
    return ModelPrice(row["input"], row["output"], row["cached"],
                      row.get("cache_write_5m"), row.get("cache_write_1h")) if row else None


PRICES = {key: price_for(key) for key in load_prices()}
CACHE_WRITE_1H_FACTOR = 2.0
CACHE_WRITE_5M_FACTOR = 1.25
CACHE_READ_FACTOR = 0.1


def _num(mapping: object, key: str) -> float:
    if not isinstance(mapping, dict):
        return 0.0
    value = mapping.get(key) or 0
    return float(value) if isinstance(value, (int, float)) else 0.0


def cache_write_input_units(usage: dict) -> float:
    """Cache-write tokens in input-price units, split by lifetime when known."""
    detail = usage.get("cache_creation")
    if isinstance(detail, dict) and ("ephemeral_1h_input_tokens" in detail
                                     or "ephemeral_5m_input_tokens" in detail):
        return (CACHE_WRITE_1H_FACTOR * _num(detail, "ephemeral_1h_input_tokens")
                + CACHE_WRITE_5M_FACTOR * _num(detail, "ephemeral_5m_input_tokens"))
    return CACHE_WRITE_5M_FACTOR * _num(usage, "cache_creation_input_tokens")


def usage_usd(price: ModelPrice, usage: dict) -> float:
    detail = usage.get("cache_creation")
    five = price.cache_write_5m
    hour = price.cache_write_1h
    cached = price.cached
    # Legacy two-field ModelPrice callers retain their documented multipliers.
    five = five if five is not None else price.input * CACHE_WRITE_5M_FACTOR
    hour = hour if hour is not None else price.input * CACHE_WRITE_1H_FACTOR
    cached = cached if cached is not None else price.input * CACHE_READ_FACTOR
    if isinstance(detail, dict) and any(k in detail for k in
            ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens")):
        write = (hour * _num(detail, "ephemeral_1h_input_tokens")
                 + five * _num(detail, "ephemeral_5m_input_tokens"))
    else:
        write = five * _num(usage, "cache_creation_input_tokens")
    return (price.input * _num(usage, "input_tokens") + write
            + cached * _num(usage, "cache_read_input_tokens")
            + price.output * _num(usage, "output_tokens")) / PER_TOKENS


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def estimate_cost(tokens: Dict[str, Any], price: Optional[Dict[str, float]]) -> Optional[float]:
    """USD for hand tokens: uncached input + cached input + output, each at its own price."""
    if not price or any(key not in price for key in TOKEN_KEYS):
        return None
    total_input = _token_count(tokens.get("input"))
    cached = _token_count(tokens.get("cached_input"))
    output = _token_count(tokens.get("output"))
    cost = (max(0, total_input - cached) * price["input"] + cached * price["cached_input"]
            + output * price["output"]) / PER_TOKENS
    return round(cost, USD_DECIMALS)


def hand_usage(tokens: Dict[str, Any]) -> Optional[Usage]:
    """Token counts of an external hand run; USD is priced later by the enrichment pass."""
    if not tokens:
        return None
    total_input = _token_count(tokens.get("input"))
    cached = _token_count(tokens.get("cached_input"))
    return Usage(read=max(0, total_input - cached), cache_read=cached,
                 cache_write=None, out=_token_count(tokens.get("output")), usd=None)
