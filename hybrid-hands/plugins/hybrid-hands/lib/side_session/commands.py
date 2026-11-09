"""Build the shell commands that `start` runs (pure, testable, used by --dry-run)."""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from . import codex_trust
from . import constants as C
from . import screen
from .config import SideConfig

SIDE_BIN = Path(__file__).resolve().parents[2] / "bin" / "side-session"
HAND_EXT_BIN = Path(__file__).resolve().parents[2] / "bin" / "hand-ext"


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
    """Codex TUI argv: model/effort, full access (no sandbox, no approval prompts)."""
    profile = ["-p", cfg.codex_profile] if cfg.codex_profile else []
    return ["codex", *profile, "-C", workdir,
            "-m", model or cfg.codex_model,
            C.CODEX_FULL_ACCESS_FLAG,
            "-c", f"model_reasoning_effort={json.dumps(effort or cfg.codex_effort)}",
            "-c", f"model_auto_compact_token_limit={C.CODEX_AUTO_COMPACT_TOKEN_LIMIT}",
            prompt]


def build_main_codex_prompt(user_prompt: str) -> str:
    """Main Sol has its own instructions and no side-session finish contract."""
    template = (Path(__file__).resolve().parents[2] / C.MAIN_CODEX_TEMPLATE_RELPATH)
    return f"{template.read_text(encoding='utf-8').strip()}\n\n{user_prompt.rstrip()}\n"


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
                  effort: str | None = None, account: str = "v1",
                  config_dir: str = "") -> tuple[list[str], dict[str, str]]:
    if provider == C.PROVIDER_CODEX:
        return (codex_argv(cfg, workdir, prompt, model, effort),
                {"CODEX_HOME": str(cfg.codex_home), C.HAND_SCOPE_ENV: uuid})
    if provider in C.EXTERNAL_PROVIDERS:
        if prompt_path is None:
            raise ValueError(f"{provider} cần prompt_path để chạy hand-ext")
        return ext_argv(provider, name, prompt_path, workdir, hours, model, effort), {}
    argv = with_chrome(cfg.claude_args, chrome_enabled(cfg, chrome))
    if cfg.status_line_cmd:
        line = {"statusLine": {"type": "command", "command": cfg.status_line_cmd}}
        argv = [*argv, "--settings", json.dumps(line, separators=(",", ":"))]
    session_flag = ["--resume", uuid] if resume else ["--session-id", uuid]
    from .config import claude_account
    config_dir = config_dir or claude_account(cfg, account)["config_dir"]
    return (["claude", *session_flag, "-n", name, *argv,
             "--model", model or C.CLAUDE_MODEL_DEFAULT,
             "--effort", effort or C.CLAUDE_EFFORT_DEFAULT, prompt],
            {"CLAUDE_CONFIG_DIR": config_dir})


def session_cmd(cfg: SideConfig, provider: str, name: str, uuid: str,
                workdir: str, prompt: str, chrome: bool | None = None,
                prompt_path: Path | None = None, hours: float | None = None,
                resume: bool = False, model: str | None = None,
                effort: str | None = None, account: str = "v1",
                config_dir: str = "") -> list[str]:
    argv, env = provider_argv(cfg, provider, name, uuid, workdir, prompt, chrome,
                              prompt_path, hours, resume, model, effort, account, config_dir)
    prelude = ""
    if provider == C.PROVIDER_CODEX:
        prelude = f"{shlex.join(codex_trust.prelude_argv(cfg.codex_home, workdir))} && "
    return screen.start_cmd(session_screen(name), argv, workdir, env,
                            unset=(C.CHILD_SESSION_ENV,), prelude=prelude)


def watch_cmd(cfg: SideConfig, name: str) -> list[str]:
    argv = [sys.executable, str(SIDE_BIN), "watch", "--name", name]
    return screen.start_cmd(watch_screen(name), argv, str(cfg.repo))
