"""Offline model pricing. Invalid overrides deliberately disable pricing."""
from __future__ import annotations

import json
import copy
from functools import lru_cache
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


def _prices() -> dict:
    from shared_config import file_stamp
    path = Path(os.environ.get(PRICING_ENV, DEFAULT_FILE)).absolute()
    return _load_prices_cached(path, file_stamp(path))


def load_prices() -> dict:
    """Return an independent copy; price lookups use the private cached table."""
    return copy.deepcopy(_prices())


@lru_cache(maxsize=32)
def _load_prices_cached(path: Path, stamp: tuple) -> dict:
    try:
        data = json.loads(path.read_text())
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
    return copy.deepcopy(_prices().get(str(model).removeprefix("opencode-go/")))


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
    from shared_config import GlobalConfigError, backends_from, load_config
    try:
        result = load_config(known_root=Path(root), config_file=getattr(cfg, "config_path", None))
    except GlobalConfigError:
        # Fatal by design (not a ValueError): never hide a broken global config here.
        raise
    except (OSError, ValueError, AttributeError):
        # An older repo-only loader failure keeps its historical "no explicit price" fallback.
        return {}
    return backends_from(result, backend)
