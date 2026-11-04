"""Follow a codex rollout file and accumulate USD from token_count events.

Rollout lines look like {"type": "event_msg", "payload": {"type": "token_count",
"info": {"total_token_usage": {...}, "last_token_usage": {...}}}}. total_token_usage
is cumulative; the delta between events is priced, with the >272K row chosen from
last_token_usage.input_tokens (the prompt size of that call).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .constants import SESSIONS_DIR
from .pricing import Tokens, cost_usd, is_long_prompt

TOKEN_COUNT_TYPE = "token_count"


def find_rollout(codex_home: Path, thread_id: str) -> Optional[Path]:
    sessions = codex_home / SESSIONS_DIR
    if not thread_id or not sessions.is_dir():
        return None
    matches = sorted(sessions.rglob(f"rollout-*{thread_id}.jsonl"))
    return matches[-1] if matches else None


class RolloutMeter:
    """Incrementally reads a rollout file; tolerant of partial trailing lines."""

    def __init__(self, prices: Dict[str, float]) -> None:
        self.prices = prices
        self.path: Optional[Path] = None
        self.offset = 0
        self.total = Tokens()
        self.usd = 0.0
        self.events = 0

    def attach(self, path: Path) -> None:
        self.path = path

    def poll(self) -> float:
        if self.path is None or not self.path.is_file():
            return self.usd
        with open(self.path, "rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
        last_newline = chunk.rfind(b"\n")
        if last_newline < 0:
            return self.usd
        self.offset += last_newline + 1
        for raw in chunk[: last_newline + 1].splitlines():
            self._consume(raw)
        return self.usd

    def _consume(self, raw: bytes) -> None:
        try:
            record = json.loads(raw)
        except ValueError:
            return
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict) or payload.get("type") != TOKEN_COUNT_TYPE:
            return
        info = payload.get("info") or {}
        total_usage = info.get("total_token_usage")
        if not isinstance(total_usage, dict):
            return
        new_total = Tokens.from_usage(total_usage)
        delta = new_total.minus(self.total)
        last = Tokens.from_usage(info.get("last_token_usage") or {})
        self.usd += cost_usd(delta, self.prices, is_long_prompt(last.input, self.prices))
        self.total = new_total
        self.events += 1
