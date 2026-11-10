"""Load project config for side-session from <git toplevel>/.claude/hybrid-hands.json."""
from __future__ import annotations

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
    claude_accounts: dict = field(default_factory=lambda: default_claude_accounts())
    provider: str = C.PROVIDER_CODEX
    claude_model: str = C.CLAUDE_MODEL_DEFAULT
    claude_effort: str = C.CLAUDE_EFFORT_DEFAULT
    claude_account: str = "v1"
    transport: str = C.TRANSPORT_PASEO
    main_session: dict = field(default_factory=dict)
    default_base: str = C.DEFAULT_BASE
    worktree_gc_auto: str = C.WORKTREE_GC_MERGED
    disk_guard: dict | None = field(default_factory=dict)
    worktree_sparse_exclude: tuple[str, ...] = ()


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


def _worktree_gc_auto(raw: object) -> str:
    """Validate policy without echoing configuration values."""
    if not isinstance(raw, dict):
        raise ValueError("side_session.worktree_gc phải là object")
    mode = raw.get("auto", C.WORKTREE_GC_MERGED)
    if not isinstance(mode, str) or mode not in C.WORKTREE_GC_MODES:
        raise ValueError("side_session.worktree_gc.auto phải là merged hoặc off")
    return mode


def _sparse_exclude(raw: object) -> tuple[str, ...]:
    """gitignore patterns to drop from new worktrees; `!` is added by side-session."""
    key = "side_session.worktree_sparse_exclude"
    if not isinstance(raw, list):
        raise ValueError(f"{key} phải là list chuỗi")
    for pattern in raw:
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError(f"{key}: mỗi pattern phải là chuỗi khác rỗng")
        if any(ch in pattern for ch in C.SPARSE_FORBIDDEN_CHARS):
            raise ValueError(f"{key}: pattern không được chứa xuống dòng/NUL")
        if pattern.startswith(C.SPARSE_NEGATE):
            raise ValueError(f"{key}: pattern không bắt đầu bằng '!' (tự thêm)")
    return tuple(raw)


def load_config(cwd: Path) -> SideConfig:
    repo = git_toplevel(cwd)
    from shared_config import load_config as load_shared
    effective = load_shared(known_root=repo).effective
    merged = effective[C.CONFIG_SECTION]
    disk_guard = effective.get("disk_guard", {})
    if disk_guard is not None and not isinstance(disk_guard, dict):
        raise ValueError("disk_guard phải là object hoặc null")
    max_parallel = merged["max_parallel"]
    if type(max_parallel) is not int or not 1 <= max_parallel <= C.MAX_PARALLEL:
        raise ValueError(f"side_session.max_parallel phải là số nguyên 1..{C.MAX_PARALLEL}")
    return SideConfig(
        repo=repo,
        worktree_gc_auto=_worktree_gc_auto(merged.get("worktree_gc", {})),
        disk_guard=disk_guard,
        worktree_sparse_exclude=_sparse_exclude(merged.get("worktree_sparse_exclude", [])),
        default_base=str(merged.get("default_base", C.DEFAULT_BASE)),
        provider=str(merged["provider"]),
        claude_model=str(merged["claude_model"]),
        claude_effort=str(merged["claude_effort"]),
        claude_account=str(merged["claude_account"]),
        transport=str(merged["transport"]),
        main_session=effective["main_session"],
        handoff_dir=_resolve(repo, merged["handoff_dir"]),
        worktree_root=_resolve(repo, merged["worktree_root"]),
        max_parallel=max_parallel,
        default_max_tokens=int(merged["default_max_tokens"]),
        watch_interval_s=float(merged["watch_interval_s"]),
        claude_args=list(merged["claude_args"]),
        state_dir=_resolve(repo, merged["state_dir"]),
        codex_home=_resolve(repo, merged["codex_home"]),
        codex_profile=str(merged["codex_profile"]),
        codex_model=str(merged["codex_model"]),
        codex_effort=str(merged["codex_effort"]),
        budget_check_cmd=_budget_cmd(repo, merged["budget_check_cmd"]),
        status_line_cmd=(str(_resolve(repo, merged["status_line_cmd"]))
                         if merged["status_line_cmd"] else ""),
        token_file=_relpath(repo, merged["token_file"], "token_file"),
        claude_accounts=load_claude_accounts(repo),
        enforce_token_cap=_bool_setting(merged["enforce_token_cap"], "enforce_token_cap"),
    )


def default_claude_accounts() -> dict:
    from copy import deepcopy
    from hand_ext.constants import DEFAULTS
    return deepcopy(DEFAULTS["claude_accounts"])


def load_claude_accounts(repo: Path) -> dict:
    """Use the canonical repo/default registry, including legacy backend overrides."""
    from hand_ext.config import load_config as load_hand_config
    return load_hand_config(known_root=repo).claude_accounts


def claude_account(cfg: SideConfig, account: str) -> dict:
    opts = cfg.claude_accounts.get(account)
    if not isinstance(opts, dict) or not isinstance(opts.get("config_dir"), str) or not opts["config_dir"]:
        raise ValueError(f"side-session: unknown/invalid Claude account {account!r}")
    return {**opts, "config_dir": str(_resolve(cfg.repo, opts["config_dir"]))}
