"""Shared helpers for the dev-workflow test suite."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "dev-workflow"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
TEMPLATES_DIR = PLUGIN_ROOT / "templates"
CONFIG_RELATIVE = Path(".claude") / "dev-workflow.toml"
SUBPROCESS_TIMEOUT_SECONDS = 30

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HAS_TOMLLIB = sys.version_info >= (3, 11)
requires_tomllib = unittest.skipUnless(HAS_TOMLLIB, "dev-workflow scripts need Python >= 3.11 (tomllib)")


def write_file(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_config(root: Path, content: str) -> Path:
    return write_file(root, CONFIG_RELATIVE.as_posix(), content)


def run_script(script: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        cwd=cwd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )
