"""Load project config for side-session from <git toplevel>/.claude/hybrid-hands.json."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import constants as C


@dataclass(frozen=True)
class SideConfig:
    repo: Path
    handoff_dir: Path
    worktree_root: Path
    max_parallel: int
    default_max_tokens: int
    watch_interval_s: float
    claude_args: list[str] = field(default_factory=list)
    state_dir: Path = Path(".")
    codex_home: Path = Path(".")
    codex_profile: str = ""


def git_toplevel(cwd: Path) -> Path:
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"side-session: not a git repo: {cwd}")
    return Path(out.stdout.strip())


def _resolve(repo: Path, raw: str) -> Path:
    path = Path(raw.replace("{repo}", repo.name)).expanduser()
    return path if path.is_absolute() else (repo / path).resolve()


def load_config(cwd: Path) -> SideConfig:
    repo = git_toplevel(cwd)
    merged = dict(C.DEFAULTS)
    cfg_file = repo / C.CONFIG_RELPATH
    if cfg_file.is_file():
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        merged.update(data.get(C.CONFIG_SECTION, {}))
    return SideConfig(
        repo=repo,
        handoff_dir=_resolve(repo, merged["handoff_dir"]),
        worktree_root=_resolve(repo, merged["worktree_root"]),
        max_parallel=int(merged["max_parallel"]),
        default_max_tokens=int(merged["default_max_tokens"]),
        watch_interval_s=float(merged["watch_interval_s"]),
        claude_args=list(merged["claude_args"]),
        state_dir=_resolve(repo, merged["state_dir"]),
        codex_home=Path(merged["codex_home"]).expanduser(),
        codex_profile=str(merged["codex_profile"]),
    )
