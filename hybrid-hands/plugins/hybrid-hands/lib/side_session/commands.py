"""Build the shell commands that `start` runs (pure, testable, used by --dry-run)."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from hand_ext.config import load_config as load_hand_ext_config

from . import codex_trust
from . import constants as C
from . import screen
from .config import SideConfig

SIDE_BIN = Path(__file__).resolve().parents[2] / "bin" / "side-session"
HAND_EXT_BIN = Path(__file__).resolve().parents[2] / "bin" / "hand-ext"
GIT_COMMON_DIR_TIMEOUT_S = 10


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


def done_path(handoff: str | Path) -> Path:
    """`<handoff>.md` -> `<handoff>.done`, the finish marker the session creates."""
    return Path(handoff).with_suffix(C.DONE_SUFFIX)


def codex_writable_roots(cfg: SideConfig, workdir: str | None = None) -> list[str]:
    """Every dir Sol's Codex sandbox must write to run hand-ext and keep its state.

    The hand-ext config is the source of truth (runs dir, worktrees, ledger/quota dirs,
    machine state and backend homes). `~/.claude` is the claude-main hand's main plan dir.
    `workdir`'s git common dir is added so `git worktree add` can write `.git/worktrees`;
    a `--worktree` workdir does not exist yet when argv is built, so fall back to the
    repo's (a linked worktree shares it).
    """
    common = _git_common_dir(workdir) or _git_common_dir(str(cfg.repo))
    roots = [cfg.worktree_root, cfg.handoff_dir, *_hand_ext_roots(cfg),
             Path(C.CLAUDE_MAIN_HOME), common]
    return list(dict.fromkeys(str(Path(root).expanduser()) for root in roots if root))


def _git_common_dir(workdir: str | None) -> Path | None:
    """Git common dir of `workdir` (the repo's `.git` when it is a linked worktree)."""
    if not workdir:
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(workdir), "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=GIT_COMMON_DIR_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    common_dir = proc.stdout.strip()
    if proc.returncode != 0 or not common_dir:
        return None
    return Path(common_dir)


def _hand_ext_roots(cfg: SideConfig) -> list[Path]:
    ext = load_hand_ext_config(cfg.repo)
    roots = [ext.runs_dir, ext.worktree_root, ext.ledger.parent,
             ext.quota_state.parent, ext.machine_state_dir]
    for name in C.HAND_EXT_BACKEND_HOMES:
        home = ext.backends.get(name, {}).get("home")
        if home:
            roots.append(Path(os.path.expanduser(str(home))))
    return roots


def chrome_enabled(cfg: SideConfig, explicit: bool | None) -> bool:
    """`--chrome`/`--no-chrome`, else whatever `claude_args` already says."""
    if explicit is not None:
        return explicit
    return C.CHROME_FLAG in cfg.claude_args and C.NO_CHROME_FLAG not in cfg.claude_args


def with_chrome(args: list[str], chrome: bool) -> list[str]:
    """Swap every `--no-chrome` for `--chrome` (or the reverse), always leaving one flag."""
    unwanted, wanted = ((C.NO_CHROME_FLAG, C.CHROME_FLAG) if chrome
                        else (C.CHROME_FLAG, C.NO_CHROME_FLAG))
    out = [wanted if part == unwanted else part for part in args]
    return out if wanted in out else [*out, wanted]


def ext_argv(provider: str, name: str, prompt_path: Path, workdir: str,
             hours: float | None = None, model: str | None = None,
             effort: str | None = None) -> list[str]:
    """`hand-ext run` argv for an external side session.

    No `--max-tokens`: hand-ext caps on input incl. cache reads, which would stop a long
    dsh run early; `side-session watch` enforces the cap without cache reads instead.
    `--hours` becomes hand-ext's `--timeout-min` so long packages are not cut at its default.
    `--model`/`--effort` are forwarded only when the caller set them explicitly.
    """
    argv = [str(HAND_EXT_BIN), "run", "--backend", provider,
            "--brief", str(prompt_path), "--label", f"{C.EXT_LABEL_PREFIX}{name}",
            "--cwd", workdir]
    if hours:
        argv += ["--timeout-min", str(max(1, round(hours * 60)))]
    if model:
        argv += ["--model", model]
    if effort:
        argv += ["--effort", effort]
    return argv


def codex_argv(cfg: SideConfig, workdir: str, prompt: str,
               model: str | None = None, effort: str | None = None) -> list[str]:
    """Codex TUI argv: model/effort, no approvals, workspace-write with network."""
    profile = ["-p", cfg.codex_profile] if cfg.codex_profile else []
    roots = json.dumps(codex_writable_roots(cfg, workdir))
    return ["codex", *profile, "-C", workdir,
            "-m", model or cfg.codex_model,
            "-a", C.CODEX_APPROVAL,
            "-s", C.CODEX_SANDBOX,
            "-c", f"model_reasoning_effort={json.dumps(effort or cfg.codex_effort)}",
            "-c", "sandbox_workspace_write.network_access=true",
            "-c", f"sandbox_workspace_write.writable_roots={roots}",
            prompt]


def build_codex_prompt(user_prompt: str, name: str, handoff: Path) -> str:
    """The Codex-specific prompt: no SendMessage, finish contract is <handoff>.done."""
    tpl = (Path(__file__).resolve().parents[2] / C.CODEX_TEMPLATE_RELPATH).read_text(
        encoding="utf-8")
    rules = (tpl.replace(C.NAME_PLACEHOLDER, name)
             .replace(C.HAND_EXT_PLACEHOLDER, str(HAND_EXT_BIN))
             .replace(C.HANDOFF_PLACEHOLDER, str(handoff))
             .replace(C.DONE_PLACEHOLDER, str(done_path(handoff))))
    return f"{user_prompt.rstrip()}\n\n{rules.strip()}\n"


def provider_argv(cfg: SideConfig, provider: str, name: str, uuid: str,
                  workdir: str, prompt: str, chrome: bool | None = None,
                  prompt_path: Path | None = None, hours: float | None = None,
                  resume: bool = False, model: str | None = None,
                  effort: str | None = None) -> tuple[list[str], dict[str, str]]:
    if provider == C.PROVIDER_CODEX:
        return (codex_argv(cfg, workdir, prompt, model, effort),
                {"CODEX_HOME": str(cfg.codex_home)})
    if provider in C.EXTERNAL_PROVIDERS:
        if prompt_path is None:
            raise ValueError(f"{provider} cần prompt_path để chạy hand-ext")
        return ext_argv(provider, name, prompt_path, workdir, hours, model, effort), {}
    argv = with_chrome(cfg.claude_args, chrome_enabled(cfg, chrome))
    if cfg.status_line_cmd:
        line = {"statusLine": {"type": "command", "command": cfg.status_line_cmd}}
        argv = [*argv, "--settings", json.dumps(line, separators=(",", ":"))]
    session_flag = ["--resume", uuid] if resume else ["--session-id", uuid]
    return (["claude", *session_flag, "-n", name, *argv, prompt], {})


def session_cmd(cfg: SideConfig, provider: str, name: str, uuid: str,
                workdir: str, prompt: str, chrome: bool | None = None,
                prompt_path: Path | None = None, hours: float | None = None,
                resume: bool = False, model: str | None = None,
                effort: str | None = None) -> list[str]:
    argv, env = provider_argv(cfg, provider, name, uuid, workdir, prompt, chrome,
                              prompt_path, hours, resume, model, effort)
    prelude = ""
    if provider == C.PROVIDER_CODEX:
        prelude = f"{shlex.join(codex_trust.prelude_argv(cfg.codex_home, workdir))} && "
    return screen.start_cmd(session_screen(name), argv, workdir, env,
                            unset=(C.CHILD_SESSION_ENV,), prelude=prelude)


def watch_cmd(cfg: SideConfig, name: str) -> list[str]:
    argv = [sys.executable, str(SIDE_BIN), "watch", "--name", name]
    return screen.start_cmd(watch_screen(name), argv, str(cfg.repo))
