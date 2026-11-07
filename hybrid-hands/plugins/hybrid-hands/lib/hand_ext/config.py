"""Load the ext_hand section of <git toplevel>/.claude/hybrid-hands.json over DEFAULTS."""
from __future__ import annotations

import copy
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parallel import validate_limit
from .constants import (
    CONFIG_SECTION, DEFAULTS, GO_USAGE_DEFAULT_DIR, GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD,
    GO_USAGE_LEDGER_NAME, GO_USAGE_LIVE_DEFAULT, GO_USAGE_LIVE_KEY, GO_USAGE_SECTION,
    GO_USAGE_STATE_DIR_ENV, ISOLATIONS, PLUGIN_PLACEHOLDER, PROJECT_CONFIG_RELPATH,
    WORKTREES_DIRNAME, MAX_PARALLEL,
)

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
    worktree_root: Path
    isolation: str
    isolation_explicit: bool
    backends: Dict[str, Dict[str, Any]]
    go_usage_ledger: Path
    go_usage_summary: Path
    go_monthly_limit_usd: float
    go_usage_live: bool
    machine_state_dir: Path
    max_parallel: int = MAX_PARALLEL

    def options(self, name: str) -> Dict[str, Any]:
        return dict(self.backends.get(name, {}))


def git_toplevel(cwd: Path) -> Path:
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd.resolve()
    return Path(out.stdout.strip())


def main_repo_root(root: Path) -> Optional[Path]:
    """Main working tree of a linked worktree: parent of the absolute git common dir."""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out.stdout.strip()).parent


def _config_path(root: Path) -> Optional[Path]:
    """Own config first; a worktree without one shares its main repo's config."""
    own = root / PROJECT_CONFIG_RELPATH
    if own.is_file():
        return own
    main = main_repo_root(root)
    if main is not None:
        path = main / PROJECT_CONFIG_RELPATH
        if path.is_file():
            return path
    return None


def _read_section(root: Path, config_file: Optional[Path] = None) -> Dict[str, Any]:
    path = config_file if config_file is not None else _config_path(root)
    if path is None or not path.is_file():
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


def merge_backends(base: Dict[str, Dict[str, Any]],
                   over: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    merged = copy.deepcopy(base)
    for name, opts in over.items():
        if not isinstance(opts, dict):
            raise ValueError(f"backends.{name} phải là object")
        merged.setdefault(name, {}).update(opts)
    return {n: {k: _expand(v) for k, v in o.items()} for n, o in merged.items()}


def _state_dir() -> Path:
    raw = os.environ.get(GO_USAGE_STATE_DIR_ENV) or GO_USAGE_DEFAULT_DIR
    return Path(os.path.expanduser(raw))


def _go_usage(root: Path, section: Dict[str, Any]) -> tuple[Path, Path, float, bool]:
    """Ledger and summary beside each other; `HYBRID_HANDS_STATE_DIR` only sets the default."""
    configured = section.get("ledger")
    ledger = (_resolve(root, str(configured)) if configured
              else _state_dir() / GO_USAGE_LEDGER_NAME)
    summary = ledger.with_name(ledger.stem + "_summary.json")
    limit = section.get("monthly_limit_usd", GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD)
    try:
        limit_usd = float(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("go_usage.monthly_limit_usd phải là số") from exc
    if limit_usd <= 0:
        raise ValueError("go_usage.monthly_limit_usd phải lớn hơn 0")
    live = section.get(GO_USAGE_LIVE_KEY, GO_USAGE_LIVE_DEFAULT)
    if not isinstance(live, bool):
        raise ValueError(f"go_usage.{GO_USAGE_LIVE_KEY} phải là true hoặc false")
    return ledger, summary, limit_usd, live


def load_config(cwd: Optional[Path] = None, *, known_root: Optional[Path] = None,
                config_file: Optional[Path] = None) -> ExtConfig:
    """Reuse caller-resolved roots/config paths within a snapshot, without caching globally."""
    root = known_root if known_root is not None else git_toplevel(Path(cwd or Path.cwd()))
    merged = copy.deepcopy(DEFAULTS)
    section = _read_section(root, config_file)
    isolation_explicit = "isolation" in section
    worktree_root_raw = section.get("worktree_root")
    go_section = section.pop(GO_USAGE_SECTION, {}) or {}
    if not isinstance(go_section, dict):
        raise ValueError(f"{CONFIG_SECTION}.{GO_USAGE_SECTION} phải là object")
    backends = merge_backends(merged["backends"], section.pop("backends", {}) or {})
    merged.update(section)
    go_ledger, go_summary, go_limit, go_live = _go_usage(root, go_section)
    max_parallel = validate_limit(merged["max_parallel"])
    max_tokens = merged["max_tokens"]
    isolation = str(merged["isolation"])
    if isolation not in ISOLATIONS:
        raise ValueError(f"{CONFIG_SECTION}.isolation phải là một trong {ISOLATIONS}")
    worktree_root = (_resolve(root, str(worktree_root_raw)) if worktree_root_raw
                     else _state_dir() / WORKTREES_DIRNAME)
    return ExtConfig(
        root=root, order=[str(n) for n in merged["order"]],
        timeout_min=float(merged["timeout_min"]),
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        sandbox=str(merged["sandbox"]),
        ledger=_resolve(root, str(merged["ledger"])),
        quota_state=_resolve(root, str(merged["quota_state"])),
        runs_dir=_resolve(root, str(merged["runs_dir"])),
        worktree_root=worktree_root.resolve(),
        isolation=isolation, isolation_explicit=isolation_explicit,
        backends=backends,
        go_usage_ledger=go_ledger, go_usage_summary=go_summary,
        go_monthly_limit_usd=go_limit,
        go_usage_live=go_live,
        machine_state_dir=_state_dir(),
        max_parallel=max_parallel,
    )
