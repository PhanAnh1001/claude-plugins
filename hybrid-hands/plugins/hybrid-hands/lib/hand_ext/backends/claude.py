"""Claude Code backend: `claude -p` on a SECOND Claude subscription (no API key).

The second login lives in its own CLAUDE_CONFIG_DIR (macOS Keychain entry is keyed to
that directory too). `--bare` is never used: it skips OAuth and the repo's hooks.
Login is checked with `claude auth status --json` (no model call); only the
`loggedIn` and `authMethod` fields are read, nothing else is printed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .. import day_budget
from ..constants import (
    CLAUDE_MAIN_BACKEND, CLAUDE_MAIN_CONFIG_DIR, CLAUDE_MAIN_EFFORT,
    CLAUDE_MAIN_MAX_DAY_PCT, CLAUDE_MAIN_MAX_TURNS, CLAUDE_MAIN_MODEL,
)
from .base import Backend, Check, Quota, RunSpec, RunState, Status, Usage, bin_for

DEFAULT_OPTIONS = {
    "config_dir": "~/.claude-hand",
    "model": "claude-opus-5-5",
    "effort": "low",
    "max_turns": 80,
}
MAIN_CONFIG_DIR = CLAUDE_MAIN_CONFIG_DIR  # the brain's plan; the hand must not share it
CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
SANDBOX_READ_ONLY = "read-only"
PERMISSION_EDIT = "acceptEdits"
PERMISSION_PLAN = "plan"
# Tools removed on read-only runs (plan mode alone still allows read-only Bash).
WRITE_TOOLS = "Edit,Write,NotebookEdit"
SYSTEM_PROMPT_FILE = "claude_append_system.md"
AUTH_TIMEOUT_S = 20  # `claude auth status` is local; generous for a cold start
OAUTH_METHODS = ("claude.ai", "oauth", "oauth_token")
RESULT_EVENT = "result"
SUBTYPE_MAX_TURNS = "error_max_turns"
SUBTYPE_MAX_BUDGET = "error_max_budget_usd"
RETRY_RATE_LIMIT = "rate_limit"
RETRY_AUTH_FAILED = "authentication_failed"
QUOTA_RE = re.compile(r"You['’]ve hit your (\w+) limit\s*[·\-]\s*resets ([^\n\"]+)")
NOT_LOGGED_IN_RE = re.compile(
    r"Invalid API key|Please run /login|not logged in|OAuth token has expired"
    r"|authentication_failed", re.IGNORECASE)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)


def parse_reset(text: str, now: Optional[datetime] = None) -> Optional[str]:
    """'3:45pm' / 'Mon 12:00am' (local time) -> ISO-8601 UTC, else None."""
    match = TIME_RE.search(text)
    if not match:
        return None
    now = now or datetime.now().astimezone()
    hour = int(match.group(1)) % 12 + (12 if match.group(3).lower() == "pm" else 0)
    when = now.replace(hour=hour, minute=int(match.group(2) or 0), second=0, microsecond=0)
    day = text.strip()[:3].lower()
    if day in WEEKDAYS:
        when += timedelta(days=(WEEKDAYS.index(day) - when.weekday()) % 7)
    if when <= now:
        when += timedelta(days=7 if day in WEEKDAYS else 1)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ClaudeBackend(Backend):
    name = "claude"
    CLI_NAME = "claude"  # both Claude backends run the same binary, different config dirs
    DEFAULT_OPTIONS = DEFAULT_OPTIONS
    ALLOW_MAIN_CONFIG_DIR = False
    BLOCKED_ENV = (
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    )

    def day_block_reason(self, options: dict) -> Optional[str]:
        if "max_day_pct" not in options:
            return None
        return ClaudeMainBackend.day_block_reason(self, options)

    def _opt(self, options: dict, key: str):
        return options.get(key, self.DEFAULT_OPTIONS[key])

    def _config_dir(self, options: dict) -> Path:
        return Path(os.path.expanduser(str(self._opt(options, "config_dir"))))

    def _base_env(self, options: dict) -> Dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k not in self.BLOCKED_ENV}
        env[CONFIG_DIR_ENV] = str(self._config_dir(options))
        return env

    def setup(self, options: dict) -> List[str]:
        cdir = self._config_dir(options)
        cdir.mkdir(parents=True, exist_ok=True)
        raw = self._opt(options, "config_dir")
        return [
            f"Config dir ready: {cdir}",
            "Log in with your SECOND Claude account (own terminal, not here):",
            f"  {CONFIG_DIR_ENV}={raw} claude",
            "  then /login (use a private browser window for the second account),",
            "  then /status to confirm the email and plan, then exit.",
        ]

    def doctor(self, options: dict) -> List[Check]:
        exe = bin_for(self.CLI_NAME)
        checks: List[Check] = []
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True,
                                 timeout=AUTH_TIMEOUT_S)
            checks.append(Check("installed", out.returncode == 0, out.stdout.strip()[:80]))
        except (OSError, subprocess.TimeoutExpired) as exc:
            return [Check("installed", False, f"{exe}: {type(exc).__name__}")]
        cdir = self._config_dir(options)
        shared = cdir.resolve() == Path(os.path.expanduser(MAIN_CONFIG_DIR)).resolve()
        if shared and not self.ALLOW_MAIN_CONFIG_DIR:
            checks.append(Check("config_dir", False, f"{cdir} is the brain's main plan dir"))
        else:
            checks.append(Check("config_dir", cdir.is_dir(),
                                str(cdir) if cdir.is_dir() else f"{cdir} missing; run setup"))
        checks.append(self._login_check(exe, options))
        leaked = [k for k in self.BLOCKED_ENV if os.environ.get(k)]
        checks.append(Check("api_env", True, "removed for runs: " + ", ".join(leaked)
                            if leaked else "no API-key env set"))
        return checks

    def _login_check(self, exe: str, options: dict) -> Check:
        try:
            out = subprocess.run([exe, "auth", "status", "--json"], capture_output=True,
                                 text=True, timeout=AUTH_TIMEOUT_S, env=self._base_env(options))
            data = json.loads(out.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            return Check("login", False, f"auth status failed: {type(exc).__name__}")
        logged_in = bool(data.get("loggedIn"))
        method = str(data.get("authMethod", "none"))
        ok = logged_in and method in OAUTH_METHODS
        detail = f"loggedIn={logged_in} authMethod={method}"
        return Check("login", ok, detail if ok else detail + "; run setup and /login")

    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        opts = spec.options
        argv = [bin_for(self.CLI_NAME), "-p", "--output-format", "stream-json", "--verbose",
                "--model", spec.model or self._opt(opts, "model"),
                "--effort", spec.effort or self._opt(opts, "effort"),
                "--max-turns", str(self._opt(opts, "max_turns"))]
        if spec.sandbox == SANDBOX_READ_ONLY:
            argv += ["--permission-mode", PERMISSION_PLAN, "--disallowedTools", WRITE_TOOLS]
        else:
            argv += ["--permission-mode", PERMISSION_EDIT]
        system_text = opts.get("append_system_prompt")
        if system_text:
            path = Path(spec.run_dir) / SYSTEM_PROMPT_FILE
            path.write_text(str(system_text), encoding="utf-8")
            argv += ["--append-system-prompt-file", str(path)]
        env_add = {CONFIG_DIR_ENV: str(self._config_dir(opts))}
        return argv, env_add, spec.prompt

    def parse_line(self, line: str, state: RunState) -> None:
        line = line.strip()
        if not line:
            return
        try:
            event = json.loads(line)
        except ValueError:
            state.extra.setdefault("raw", []).append(line[:500])
            return
        if not isinstance(event, dict):
            return
        if event.get("type") == "system" and event.get("subtype") == "api_retry":
            state.extra.setdefault("retry_errors", []).append(str(event.get("error", "")))
        if event.get("type") == RESULT_EVENT:
            self._read_result(event, state)

    @staticmethod
    def _read_result(event: dict, state: RunState) -> None:
        state.final_text = str(event.get("result") or "")
        state.extra["subtype"] = event.get("subtype")
        state.extra["is_error"] = bool(event.get("is_error"))
        usage = Usage()
        for model_usage in (event.get("modelUsage") or {}).values():
            cache_read = int(model_usage.get("cacheReadInputTokens", 0))
            usage.input += (int(model_usage.get("inputTokens", 0)) + cache_read
                            + int(model_usage.get("cacheCreationInputTokens", 0)))
            usage.cached_input += cache_read
            usage.output += int(model_usage.get("outputTokens", 0))
        state.usage = usage

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        retries = state.extra.get("retry_errors", [])
        blob = "\n".join([state.final_text, stderr_text,
                          *state.extra.get("raw", []), *state.errors])
        quota = QUOTA_RE.search(blob)
        if quota or (RETRY_RATE_LIMIT in retries and exit_code != 0):
            state.quota = Quota(exhausted=True, window=quota.group(1) if quota else None,
                                resets_at=parse_reset(quota.group(2)) if quota else None)
            return Status.QUOTA
        if NOT_LOGGED_IN_RE.search(blob) or RETRY_AUTH_FAILED in retries:
            return Status.NOT_LOGGED_IN
        subtype = state.extra.get("subtype")
        if subtype in (SUBTYPE_MAX_TURNS, SUBTYPE_MAX_BUDGET):
            return Status.CAPPED
        if exit_code == 0 and not state.extra.get("is_error") and subtype == "success":
            return Status.OK
        if stderr_text.strip():
            state.errors.append(stderr_text.strip()[-500:])
        return Status.FAILED


class ClaudeMainBackend(ClaudeBackend):
    """Claude on the PRIMARY subscription (`~/.claude`): explicit, Opus, low effort.

    It refuses to run once this machine has used `max_day_pct` of the weekly limit today,
    measured over the whole machine (brain, hands and this backend).
    """
    name = CLAUDE_MAIN_BACKEND
    DEFAULT_OPTIONS = {
        "config_dir": CLAUDE_MAIN_CONFIG_DIR,
        "model": CLAUDE_MAIN_MODEL,
        "effort": CLAUDE_MAIN_EFFORT,
        "max_turns": CLAUDE_MAIN_MAX_TURNS,
        "max_day_pct": CLAUDE_MAIN_MAX_DAY_PCT,
    }
    ALLOW_MAIN_CONFIG_DIR = True
    # Claude Code reads ~/.claude.json while CLAUDE_CONFIG_DIR is unset; pointing it at
    # ~/.claude makes Claude Code look for ~/.claude/.claude.json and report "Not logged in".
    # Blocking the name also strips a value inherited from the parent environment.
    BLOCKED_ENV = ClaudeBackend.BLOCKED_ENV + (CONFIG_DIR_ENV,)

    def _base_env(self, options: dict) -> Dict[str, str]:
        env = super()._base_env(options)
        if self._config_dir(options).resolve() == Path(os.path.expanduser(MAIN_CONFIG_DIR)).resolve():
            env.pop(CONFIG_DIR_ENV, None)
        return env

    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        argv, env_add, stdin = super().build_command(spec)
        if self._config_dir(spec.options).resolve() == Path(os.path.expanduser(MAIN_CONFIG_DIR)).resolve():
            env_add.pop(CONFIG_DIR_ENV, None)
        return argv, env_add, stdin

    def setup(self, options: dict) -> List[str]:
        cdir = self._config_dir(options)
        cdir.mkdir(parents=True, exist_ok=True)
        return [f"Config dir ready: {cdir}",
                "Uses the PRIMARY Claude subscription (already logged in); no second login."]

    def day_block_reason(self, options: dict) -> Optional[str]:
        """None when the machine is under the day cap, else the reason the run must stop."""
        try:
            use = day_budget.assess(options)
        except day_budget.BudgetUnavailable as exc:
            return (f"không tính được mức dùng Claude hôm nay ({exc}); "
                    "ghi yêu cầu vào bàn giao để Opus quyết")
        if use.blocked:
            return (f"máy này đã dùng {use.pct:.1f}% Claude hôm nay "
                    f"(ngưỡng {use.max_pct:g}%); ghi yêu cầu vào bàn giao để Opus quyết")
        return None


class ClaudeAccountBackend(ClaudeMainBackend):
    """A configured numbered account; primary-home OAuth semantics follow the path."""

    def __init__(self, name: str):
        self.name = name
        account = name[len("claude-"):]
        self.DEFAULT_OPTIONS = {**DEFAULT_OPTIONS,
                                "config_dir": "~/.claude" if account == "v1" else "~/.claude-hand"}

    def setup(self, options: dict) -> List[str]:
        cdir = self._config_dir(options)
        if cdir.resolve() == Path(os.path.expanduser(MAIN_CONFIG_DIR)).resolve():
            return super().setup(options)
        cdir.mkdir(parents=True, exist_ok=True)
        return [f"Config dir ready: {cdir}",
                f"Log in to this Claude account in your terminal: {CONFIG_DIR_ENV}={cdir} claude",
                "then /login, /status, and exit."]

    def day_block_reason(self, options: dict) -> Optional[str]:
        if "max_day_pct" not in options:
            return None
        return super().day_block_reason(options)
