"""Read the canonical hybrid-hands price file(s); no standalone price defaults."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re


def version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", path.parent.parent.name))


PLUGIN_SUBDIR = "plugins/hybrid-hands"
PRICES_RELATIVE = "config/model-prices.json"


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude")))


def marketplace_sources() -> list[Path]:
    """Local directory marketplaces are the live source; the cache may lag (Fable missing in 0.55.0)."""
    try:
        data = json.loads((claude_home() / "plugins/known_marketplaces.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    found = []
    for entry in data.values():
        source = entry.get("source") if isinstance(entry, dict) else None
        path = source.get("path") if isinstance(source, dict) else None
        if isinstance(path, str) and (Path(path) / PLUGIN_SUBDIR).is_dir():
            found.append(Path(path) / PLUGIN_SUBDIR)
    return found


def plugin_candidates() -> list[Path]:
    repo = Path(__file__).resolve().parents[4]
    source = repo / "hybrid-hands" / PLUGIN_SUBDIR
    installed = list((claude_home() / "plugins/cache").glob(f"*/hybrid-hands/*/{PRICES_RELATIVE}"))
    return ([source] + marketplace_sources()
            + [p.parent.parent for p in sorted(installed, key=version_key, reverse=True)])


def read_models(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != 1:
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        return {}
    return {model: row for model, row in models.items() if valid_row(row)}


def valid_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def valid_row(row: object) -> bool:
    required = ("input", "cached", "output")
    optional = ("cache_write_5m", "cache_write_1h")
    return (isinstance(row, dict) and all(valid_number(row.get(k)) for k in required)
            and all(k not in row or valid_number(row[k]) for k in optional))


def load_prices() -> dict:
    """One canonical table per model: the first candidate that prices a model wins."""
    override = os.environ.get("HYBRID_HANDS_PRICING_FILE")
    if override:
        return read_models(Path(override))
    merged: dict = {}
    for root in plugin_candidates():
        path = root / PRICES_RELATIVE
        if path.is_file():
            for model, row in read_models(path).items():
                merged.setdefault(model, row)
    return merged
