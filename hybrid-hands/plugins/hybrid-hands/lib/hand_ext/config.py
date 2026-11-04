"""Load the ext_hand section of <git toplevel>/.claude/hybrid-hands.json over DEFAULTS."""
from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import CONFIG_SECTION, DEFAULTS, PLUGIN_PLACEHOLDER, PROJECT_CONFIG_RELPATH

PLUGIN_DIR = Path(__file__).resolve().parents[2]


@dataclass
class ExtConfig:
    root: Path
    order: List[str]
    timeout_min: float
    max_tokens: Optional[int]
    sandbox: str
    ledger: Path
    quota_state: Path
    runs_dir: Path
    backends: Dict[str, Dict[str, Any]]

    def options(self, name: str) -> Dict[str, Any]:
        return dict(self.backends.get(name, {}))


def git_toplevel(cwd: Path) -> Path:
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd.resolve()
    return Path(out.stdout.strip())


def _read_section(root: Path) -> Dict[str, Any]:
    path = root / PROJECT_CONFIG_RELPATH
    if not path.is_file():
        return {}
    section = json.loads(path.read_text(encoding="utf-8")).get(CONFIG_SECTION, {})
    if not isinstance(section, dict):
        raise ValueError(f"{path}: '{CONFIG_SECTION}' phải là object")
    return section


def _resolve(root: Path, value: str) -> Path:
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else root / path


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(PLUGIN_PLACEHOLDER, str(PLUGIN_DIR))
    return value


def merge_backends(base: Dict[str, Dict[str, Any]], over: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    merged = copy.deepcopy(base)
    for name, opts in over.items():
        if not isinstance(opts, dict):
            raise ValueError(f"backends.{name} phải là object")
        merged.setdefault(name, {}).update(opts)
    return {n: {k: _expand(v) for k, v in o.items()} for n, o in merged.items()}


def load_config(cwd: Optional[Path] = None) -> ExtConfig:
    root = git_toplevel(Path(cwd or Path.cwd()))
    merged = copy.deepcopy(DEFAULTS)
    section = _read_section(root)
    backends = merge_backends(merged["backends"], section.pop("backends", {}) or {})
    merged.update(section)
    max_tokens = merged["max_tokens"]
    return ExtConfig(
        root=root, order=[str(n) for n in merged["order"]],
        timeout_min=float(merged["timeout_min"]),
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        sandbox=str(merged["sandbox"]),
        ledger=_resolve(root, str(merged["ledger"])),
        quota_state=_resolve(root, str(merged["quota_state"])),
        runs_dir=_resolve(root, str(merged["runs_dir"])),
        backends=backends,
    )
