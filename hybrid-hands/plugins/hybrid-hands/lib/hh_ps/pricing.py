"""Claude model prices, USD estimates and Go hand estimates for `hh-ps`.

Ported from statusline plugins/statusline/scripts/usage_ledger.py (the USD/MTok
price table, family fallback, cache multipliers and the usage formula).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from hand_ext.constants import GO_USAGE_BACKENDS
from hand_ext.go_usage import estimate_cost, price_for as go_price_for

from .models import Usage

PER_TOKENS = 1_000_000
SYNTHETIC_MODEL = "<synthetic>"
GO_HAND_PRICE = go_price_for(None)


@dataclass(frozen=True)
class ModelPrice:
    input: float   # USD per million input tokens
    output: float  # USD per million output tokens


# Anthropic first-party API list prices, USD per million tokens (data of 10/2026):
#   https://platform.claude.com/docs/en/about-claude/pricing
PRICES = {
    "claude-opus-5-5": ModelPrice(4.00, 20.00),
    "claude-sonnet-5-5": ModelPrice(2.00, 10.00),
    "claude-haiku-5-5": ModelPrice(0.10, 0.50),
}
# Unknown model ids fall back to the 5.5 price of their family.
FAMILY_FALLBACK = (("opus", "claude-opus-5-5"), ("sonnet", "claude-sonnet-5-5"),
                   ("haiku", "claude-haiku-5-5"))
# Cache multipliers on the input price (Anthropic prompt-caching pricing).
CACHE_WRITE_1H_FACTOR = 2.0
CACHE_WRITE_5M_FACTOR = 1.25
CACHE_READ_FACTOR = 0.1


def price_for(model: str) -> Optional[ModelPrice]:
    if model in PRICES:
        return PRICES[model]
    name = model.lower()
    for family, model_id in FAMILY_FALLBACK:
        if family in name:
            return PRICES[model_id]
    return None


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
    input_units = (_num(usage, "input_tokens") + cache_write_input_units(usage)
                   + CACHE_READ_FACTOR * _num(usage, "cache_read_input_tokens"))
    return (input_units * price.input + _num(usage, "output_tokens") * price.output) / PER_TOKENS


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def hand_usage(tokens: Dict[str, Any], backend: str) -> Optional[Usage]:
    """Usage of an external hand run: its registry totals plus the Go estimate."""
    if not tokens:
        return None
    total_input = _token_count(tokens.get("input"))
    cached = _token_count(tokens.get("cached_input"))
    usd = None
    if backend in GO_USAGE_BACKENDS:
        usd = estimate_cost({"input": total_input, "cached_input": cached,
                             "output": _token_count(tokens.get("output"))},
                            GO_HAND_PRICE)
    return Usage(read=max(0, total_input - cached), cache_read=cached,
                 cache_write=None, out=_token_count(tokens.get("output")), usd=usd)
