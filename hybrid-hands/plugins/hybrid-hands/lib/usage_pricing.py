"""Offline model pricing. Invalid overrides deliberately disable pricing."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Optional

PRICING_ENV = "HYBRID_HANDS_PRICING_FILE"
DEFAULT_FILE = Path(__file__).resolve().parents[1] / "config" / "model-prices.json"
REQUIRED = ("input", "cached", "output")
OPTIONAL = ("cache_write_5m", "cache_write_1h")


def number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) and result >= 0 else None


def load_prices() -> dict:
    try:
        data = json.loads(Path(os.environ.get(PRICING_ENV, DEFAULT_FILE)).read_text())
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != 1:
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        return {}
    return {key: row for key, row in models.items() if isinstance(row, dict)
            and all(number(row.get(k)) is not None for k in REQUIRED)
            and all(k not in row or number(row[k]) is not None for k in OPTIONAL)}


def model_price(model: str) -> Optional[dict]:
    return load_prices().get(str(model).removeprefix("opencode-go/"))


def token_price(model: str) -> Optional[dict]:
    row = model_price(model)
    return ({"input": row["input"], "cached_input": row["cached"],
             "output": row["output"]} if row else None)


def explicit_options(cfg: Any, backend: str) -> dict:
    """Read only the explicit backend config, without merged legacy price defaults."""
    if cfg is None:
        return {}
    root = getattr(cfg, "root", None)
    if root is None:
        return cfg.options(backend)
    # Delay import because config constants import pricing helpers.
    from hand_ext.config import _config_path
    path = getattr(cfg, "config_path", None) or _config_path(Path(root))
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text())
        options = data.get("ext_hand", {}).get("backends", {}).get(backend, {})
    except (OSError, ValueError, AttributeError, TypeError):
        return {}
    return options if isinstance(options, dict) else {}
