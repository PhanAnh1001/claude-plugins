"""Effective Claude accounts (``ext_hand.claude_accounts``) and their config homes.

Moved from the retired index store; used by the Claude USD~/1% calibration.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

UNKNOWN_ACCOUNT = ""


def _expand(raw: str, root: Path) -> Path:
    if raw == "~" or raw.startswith("~/"):
        path = Path.home() / raw[2:] if raw != "~" else Path.home()
    else:
        path = Path(raw)
    return (path if path.is_absolute() else root / path).resolve()


@lru_cache(maxsize=8)
def _account_homes(home_key: str, config_key: str, cwd: str) -> Dict[str, Path]:
    from hand_ext.constants import DEFAULTS
    accounts: Any = DEFAULTS["claude_accounts"]
    try:
        from shared_config import load_config
        accounts = load_config(known_root=Path(cwd)).effective["ext_hand"]["claude_accounts"]
    except Exception:  # noqa: BLE001 - any config failure keeps the plugin defaults
        pass
    found: Dict[str, Path] = {}
    for name, entry in (accounts.items() if isinstance(accounts, dict) else ()):
        raw = entry.get("config_dir") if isinstance(entry, dict) else None
        if isinstance(raw, str) and raw.strip():
            try:
                found[str(name)] = _expand(raw.strip(), Path(cwd))
            except (OSError, RuntimeError):
                continue
    return found


def account_homes() -> Dict[str, Path]:
    """Effective Claude account name -> resolved config home."""
    return dict(_account_homes(str(Path.home()), os.environ.get("HYBRID_HANDS_CONFIG", ""),
                               str(Path.cwd())))


def account_for_home(home: Path) -> str:
    try:
        resolved = Path(home).resolve()
    except (OSError, RuntimeError):
        return UNKNOWN_ACCOUNT
    matches = [name for name, path in account_homes().items() if path == resolved]
    return matches[0] if len(matches) == 1 else UNKNOWN_ACCOUNT
