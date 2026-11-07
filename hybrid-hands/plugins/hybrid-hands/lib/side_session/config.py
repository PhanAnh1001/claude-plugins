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
    codex_model: str = C.CODEX_MODEL_DEFAULT
    codex_effort: str = C.CODEX_EFFORT_DEFAULT
    budget_check_cmd: list[str] = field(default_factory=list)
    status_line_cmd: str = ""
    token_file: str = ""
    enforce_token_cap: bool = True


def git_toplevel(cwd: Path) -> Path:
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"side-session: not a git repo: {cwd}")
    return Path(out.stdout.strip())


def _resolve(repo: Path, raw: str) -> Path:
    path = Path(raw.replace("{repo}", repo.name)).expanduser()
    return path if path.is_absolute() else (repo / path).resolve()


def _budget_cmd(repo: Path, raw: object) -> list[str]:
    """argv of the day-budget guard; a relative first element is resolved from the repo."""
    if not isinstance(raw, list) or not all(isinstance(part, str) and part for part in raw):
        raise ValueError(f"side_session.budget_check_cmd phải là list chuỗi, nhận {raw!r}")
    argv = list(raw)
    if argv:
        first = Path(argv[0]).expanduser()
        argv[0] = str(first if first.is_absolute() else (repo / first).resolve())
    return argv


def _relpath(repo: Path, raw: object, key: str) -> str:
    """A repo-relative path setting; the empty string disables it."""
    if not isinstance(raw, str):
        raise ValueError(f"side_session.{key} phải là chuỗi, nhận {raw!r}")
    return str(_resolve(repo, raw)) if raw else ""


def _bool_setting(raw: object, key: str) -> bool:
    """A boolean setting; integers are rejected because JSON `1` is not a bool."""
    if not isinstance(raw, bool):
        raise ValueError(f"side_session.{key} phải là bool, nhận {raw!r}")
    return raw


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
        codex_model=str(merged["codex_model"]),
        codex_effort=str(merged["codex_effort"]),
        budget_check_cmd=_budget_cmd(repo, merged["budget_check_cmd"]),
        status_line_cmd=(str(_resolve(repo, merged["status_line_cmd"]))
                         if merged["status_line_cmd"] else ""),
        token_file=_relpath(repo, merged["token_file"], "token_file"),
        enforce_token_cap=_bool_setting(merged["enforce_token_cap"], "enforce_token_cap"),
    )
