"""Shared helpers for the statusline plugin tests.

Ported from dev-workflow (commit 65f7f95) tests/_support.py; trimmed to what these tests need.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

MARKETPLACE_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = MARKETPLACE_ROOT / "plugins" / "statusline"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
SUBPROCESS_TIMEOUT_SECONDS = 30
# Env vars that would leak the developer's real Claude config into a test run.
LEAKY_ENV_VARS = ("CLAUDE_HOME", "STATUSLINE_JSON_BACKEND", "STATUSLINE_LAST_SKILL_MAX_BYTES")


def clean_env(**overrides: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in LEAKY_ENV_VARS}
    env.update(overrides)
    return env


def run_bash(
    script: Path, args: list[str], env: dict[str, str], stdin: str = "", cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args], input=stdin, env=env, cwd=cwd, capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )
