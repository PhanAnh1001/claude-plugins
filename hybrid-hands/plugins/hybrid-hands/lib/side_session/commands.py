"""Build the shell commands that `start` runs (pure, testable, used by --dry-run)."""
from __future__ import annotations

import sys
from pathlib import Path

from . import constants as C
from . import screen
from .config import SideConfig

SIDE_BIN = Path(__file__).resolve().parents[2] / "bin" / "side-session"


def session_screen(name: str) -> str:
    return f"{C.SCREEN_PREFIX}{name}"


def watch_screen(name: str) -> str:
    return f"{session_screen(name)}{C.WATCH_SUFFIX}"


def max_tokens_for(cfg: SideConfig, explicit: int | None, hours: float | None) -> int:
    if explicit:
        return explicit
    if hours:
        return max(cfg.default_max_tokens, int(C.TOKENS_PER_HOUR * hours))
    return cfg.default_max_tokens


def worktree_cmd(cfg: SideConfig, name: str, base: str) -> list[str]:
    return ["git", "-C", str(cfg.repo), "worktree", "add",
            str(cfg.worktree_root / name), "-b", f"{C.BRANCH_PREFIX}{name}", base]


def provider_argv(cfg: SideConfig, provider: str, name: str, uuid: str,
                  workdir: str, prompt: str) -> tuple[list[str], dict[str, str]]:
    if provider == C.PROVIDER_CODEX:
        profile = ["-p", cfg.codex_profile] if cfg.codex_profile else []
        return (["codex", *profile, "-C", workdir, prompt],
                {"CODEX_HOME": str(cfg.codex_home)})
    return (["claude", "--session-id", uuid, "-n", name, *cfg.claude_args, prompt], {})


def session_cmd(cfg: SideConfig, provider: str, name: str, uuid: str,
                workdir: str, prompt: str) -> list[str]:
    argv, env = provider_argv(cfg, provider, name, uuid, workdir, prompt)
    return screen.start_cmd(session_screen(name), argv, workdir, env)


def watch_cmd(cfg: SideConfig, name: str) -> list[str]:
    argv = [sys.executable, str(SIDE_BIN), "watch", "--name", name]
    return screen.start_cmd(watch_screen(name), argv, str(cfg.repo))
