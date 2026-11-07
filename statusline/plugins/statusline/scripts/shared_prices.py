"""Locate the canonical hybrid-hands price file; no standalone price defaults."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re


def version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", path.parent.parent.name))


def plugin_candidates() -> list[Path]:
    repo = Path(__file__).resolve().parents[4]
    source = repo / "hybrid-hands/plugins/hybrid-hands"
    cache = Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude"))) / "plugins/cache"
    installed = list(cache.glob("*/hybrid-hands/*/config/model-prices.json"))
    return [source] + [p.parent.parent for p in sorted(installed, key=version_key, reverse=True)]


def load_prices() -> dict:
    override = os.environ.get("HYBRID_HANDS_PRICING_FILE")
    candidates = ([Path(override)] if override else
                  [p / "config/model-prices.json" for p in plugin_candidates()])
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != 1:
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        return {}
    required = ("input", "cached", "output")
    optional = ("cache_write_5m", "cache_write_1h")
    def valid(value: object) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value) and value >= 0
        except OverflowError:
            return False
    return {model: row for model, row in models.items() if isinstance(row, dict)
            and all(valid(row.get(k)) for k in required)
            and all(k not in row or valid(row[k]) for k in optional)}
