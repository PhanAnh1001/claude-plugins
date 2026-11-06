"""Backend interface for hand-ext: one subscription CLI (codex, claude, opencode, gemini).

Conventions:
- Each backend reads its binary from env `HAND_EXT_<NAME>_BIN` (e.g. HAND_EXT_CODEX_BIN),
  falling back to the CLI name on PATH. Tests point it at a fake script. Use `bin_for()`.
- `BLOCKED_ENV` names are removed from the child environment so a run never bills an API key.
- Module `backends/<name>.py` defines class `<Name>Backend` (registry loads it lazily).
"""
from __future__ import annotations

import os
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BIN_ENV_TEMPLATE = "HAND_EXT_{name}_BIN"
# OpenCode Go temporarily refuses prefills under load: 429 with Retry-After 30 s. This is
# capacity pressure, not the plan limit, so it must not enter quota_state.
CAPACITY_PATTERN = re.compile(
    r"prefill_cap_refused|at capacity|retry shortly", re.IGNORECASE)
CAPACITY_NOTE = ("Go quá tải tạm thời (prefill_cap_refused), không phải hết hạn mức; "
                 "backend đã tự thử lại theo retryPolicy; chạy lại sau ít phút")


def is_capacity_error(text: str) -> bool:
    """True when the output carries OpenCode Go's transient capacity refusal."""
    return bool(CAPACITY_PATTERN.search(text or ""))


class Status(str, Enum):
    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CAPPED = "capped"
    QUOTA = "quota_exhausted"
    NOT_LOGGED_IN = "not_logged_in"


@dataclass
class Usage:
    input: int = 0
    cached_input: int = 0
    output: int = 0

    def total(self) -> int:
        return self.input + self.output


@dataclass
class Quota:
    used_percent: Optional[float] = None
    resets_at: Optional[str] = None  # ISO-8601 UTC
    window: Optional[str] = None
    exhausted: bool = False


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True  # optional checks are reported but never fail doctor/auto


@dataclass
class RunSpec:
    prompt: str
    cwd: Path
    run_dir: Path
    model: str
    effort: str
    sandbox: str
    timeout_s: int
    max_tokens: Optional[int]
    options: dict  # section backends.<name> of the config
    browser: bool = False  # mount the Playwright MCP server (dsh only)


@dataclass
class RunState:
    usage: Usage
    quota: Optional[Quota] = None
    final_text: str = ""
    errors: List[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


def bin_for(name: str) -> str:
    """Binary for backend `name`: $HAND_EXT_<NAME>_BIN, else `name` on PATH."""
    override = os.environ.get(BIN_ENV_TEMPLATE.format(name=name.upper()))
    return override or shutil.which(name) or name


class Backend(ABC):
    name: str = ""
    BLOCKED_ENV: Tuple[str, ...] = ()

    @abstractmethod
    def setup(self, options: dict) -> List[str]:
        """Idempotent; return message lines incl. the login command the user runs."""

    @abstractmethod
    def doctor(self, options: dict) -> List[Check]:
        """Installed, version, subscription login (not API key), config. Never print secrets."""

    @abstractmethod
    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        """Return argv, extra env, stdin text."""

    @abstractmethod
    def parse_line(self, line: str, state: RunState) -> None:
        """Handle one stdout line."""

    def poll(self, spec: RunSpec, state: RunState) -> None:
        """Called about every second while the child runs."""
        return None

    @abstractmethod
    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        """Classify the run, recognising quota exhaustion and missing login."""
