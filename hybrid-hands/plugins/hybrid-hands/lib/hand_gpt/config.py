"""Load the gpt_hand section of <git toplevel>/.claude/hybrid-hands.json over defaults."""
from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import CONFIG_SECTION, DEFAULTS, PROJECT_CONFIG_RELPATH


@dataclass
class HandConfig:
    root: Path
    codex_home: Path
    model: str
    service_tier: str
    effort: str
    sandbox: str
    max_usd: float
    approval_usd: float
    timeout_min: float
    ledger: Path
    runs_dir: Path
    prices: Dict[str, float]


def git_toplevel(cwd: Path) -> Path:
    """Return the git toplevel of cwd, or cwd itself outside a repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd.resolve()
    return Path(out.stdout.strip())


def _read_section(root: Path) -> Dict[str, Any]:
    path = root / PROJECT_CONFIG_RELPATH
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    section = data.get(CONFIG_SECTION, {})
    if not isinstance(section, dict):
        raise ValueError(f"{path}: '{CONFIG_SECTION}' must be an object")
    return section


def _resolve(root: Path, value: str) -> Path:
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else root / path


def load_config(cwd: Optional[Path] = None) -> HandConfig:
    root = git_toplevel(Path(cwd or Path.cwd()))
    merged = copy.deepcopy(DEFAULTS)
    section = _read_section(root)
    prices = dict(merged["prices"])
    prices.update(section.get("prices", {}))
    merged.update(section)
    merged["prices"] = prices
    return HandConfig(
        root=root,
        codex_home=Path(os.path.expanduser(str(merged["codex_home"]))),
        model=str(merged["model"]),
        service_tier=str(merged["service_tier"]),
        effort=str(merged["effort"]),
        sandbox=str(merged["sandbox"]),
        max_usd=float(merged["max_usd"]),
        approval_usd=float(merged["approval_usd"]),
        timeout_min=float(merged["timeout_min"]),
        ledger=_resolve(root, str(merged["ledger"])),
        runs_dir=_resolve(root, str(merged["runs_dir"])),
        prices={k: float(v) for k, v in prices.items()},
    )
