"""Map session directories to repo roots and merge side-session state across repos.

`hh-ps` lists live sessions of every project, so a side session whose state
lives in another repo must still be loaded to nest under its parent.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .registry_source import (
    PsConfig, SessionMeta, load_ps_config, load_session_meta, side_state_caps,
)

SideMap = Dict[str, Dict[str, Any]]
GIT_DIR_NAME = ".git"


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(["git", "-C", str(cwd), "rev-parse", *args],
                              capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return done.stdout.strip() or None


def project_root(cwd: Path) -> Path:
    found = _git(cwd, "--show-toplevel")
    return Path(found) if found else cwd.resolve()


def main_repo_root(cwd: Path) -> Optional[Path]:
    """Root of the main checkout, so a worktree maps to the repo that owns it."""
    found = _git(cwd, "--path-format=absolute", "--git-common-dir")
    if not found:
        return None
    common = Path(found)
    return common.parent if common.name == GIT_DIR_NAME else common


@dataclass
class RepoState:
    """Side state and launcher meta merged over every loaded repo root."""
    side: SideMap = field(default_factory=dict)
    meta: Dict[str, SessionMeta] = field(default_factory=dict)
    roots: List[Path] = field(default_factory=list)
    _by_cwd: Dict[str, Optional[Path]] = field(default_factory=dict)

    def add_root(self, root: Path, config: Optional[PsConfig] = None) -> bool:
        """Load one repo once; returns True when it brought new side sessions."""
        root = root.resolve()
        if root in self.roots:
            return False
        self.roots.append(root)
        if config is None:
            try:
                config = load_ps_config(root)
            except (OSError, ValueError):
                return False  # a broken config elsewhere must not break this view
        before = len(self.side)
        for uuid, state in side_state_caps(config).items():
            self.side.setdefault(uuid, state)
        for uuid, found in load_session_meta(config).items():
            self.meta.setdefault(uuid, found)
        return len(self.side) > before

    def add_cwds(self, cwds: Iterable[str]) -> bool:
        """Load the repo of each new directory; git runs once per directory."""
        grew = False
        for raw in cwds:
            if not raw or raw in self._by_cwd:
                continue
            path = Path(raw)
            root = main_repo_root(path) if path.is_dir() else None
            self._by_cwd[raw] = root
            if root is not None and self.add_root(root):
                grew = True
        return grew
