"""Token accounting and USD pricing (normal vs >272K-token prompts)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

from .constants import TOKENS_PER_PRICE_UNIT


@dataclass
class Tokens:
    input: int = 0  # includes cached_input (OpenAI usage convention)
    cached_input: int = 0
    output: int = 0

    @classmethod
    def from_usage(cls, usage: Dict) -> "Tokens":
        return cls(
            input=int(usage.get("input_tokens", 0) or 0),
            cached_input=int(usage.get("cached_input_tokens", 0) or 0),
            output=int(usage.get("output_tokens", 0) or 0),
        )

    def minus(self, other: "Tokens") -> "Tokens":
        return Tokens(
            max(0, self.input - other.input),
            max(0, self.cached_input - other.cached_input),
            max(0, self.output - other.output),
        )

    def plus(self, other: "Tokens") -> "Tokens":
        return Tokens(
            self.input + other.input,
            self.cached_input + other.cached_input,
            self.output + other.output,
        )

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


def is_long_prompt(prompt_tokens: int, prices: Dict[str, float]) -> bool:
    return prompt_tokens > prices["long_threshold"]


def cost_usd(tokens: Tokens, prices: Dict[str, float], long_prompt: bool = False) -> float:
    """USD for tokens; long_prompt selects the >threshold price row."""
    prefix = "long_" if long_prompt else ""
    uncached = max(0, tokens.input - tokens.cached_input)
    total = (
        uncached * prices[prefix + "input"]
        + tokens.cached_input * prices[prefix + "cached_input"]
        + tokens.output * prices[prefix + "output"]
    )
    return total / TOKENS_PER_PRICE_UNIT


def cost_for_call(tokens: Tokens, prices: Dict[str, float]) -> float:
    """USD for one model call, choosing the price row from that call's prompt size."""
    return cost_usd(tokens, prices, is_long_prompt(tokens.input, prices))
