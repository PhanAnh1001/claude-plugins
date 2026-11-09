"""Read-only native eligibility checks; environment markers are not tool discovery."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from .config import ExtConfig, PLUGIN_DIR

HAND_AGENT = Path("agents/hand.md")
CODEX_MARKER = "CODEX_THREAD_ID"
CLAUDE_MARKER = "CLAUDECODE"
FRONTMATTER_KEYS = ("model", "effort")


def _provider(name: str) -> str:
    if name == "codex":
        return name
    if name in ("claude", "claude-main") or re.fullmatch(r"claude-v[1-9][0-9]*", name):
        return "claude"
    return ""


def _caller(env: Mapping[str, str]) -> str:
    codex = bool(env.get(CODEX_MARKER))
    claude = env.get(CLAUDE_MARKER) == "1"
    # A parent Claude session ID may be inherited by Codex; only active markers count.
    if codex == claude:
        return ""
    return "codex" if codex else "claude"


def _same_account(provider: str, options: dict, env: Mapping[str, str]) -> bool:
    if provider == "codex":
        current = env.get("CODEX_HOME") or "~/.codex"
        selected = options.get("home")
    else:
        current = env.get("CLAUDE_CONFIG_DIR") or "~/.claude"
        selected = options.get("config_dir")
    if not isinstance(selected, str) or not selected:
        return False
    return Path(current).expanduser().resolve() == Path(selected).expanduser().resolve()


def _agent_settings(plugin_dir: Path) -> tuple[dict[str, str], str]:
    try:
        text = (plugin_dir / HAND_AGENT).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}, "Claude hand frontmatter unavailable"
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}, "Claude hand frontmatter invalid"
    settings: dict[str, str] = {}
    for line in lines[1:lines.index("---", 1)]:
        key, separator, value = line.partition(":")
        if key not in FRONTMATTER_KEYS:
            continue
        value = value.strip()
        if not separator or not value or key in settings:
            return {}, "Claude hand frontmatter invalid"
        # Only scalar identifiers are supported; fail closed on YAML constructs.
        if value[:1] in ("'", '"') and value[-1:] == value[:1]:
            value = value[1:-1]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            return {}, "Claude hand frontmatter invalid"
        settings[key] = value
    if set(settings) != set(FRONTMATTER_KEYS):
        return {}, "Claude hand frontmatter missing model/effort"
    return settings, ""


def native_selection(cfg: ExtConfig, name: str) -> tuple[bool, str]:
    """Return policy eligibility, without dispatching or changing preflight decisions.

    Never probe credentials, runtime config or RPC. Environment markers establish
    caller identity only; the caller must still verify native tool capability.
    For Codex, the caller must select the model/effort in pick's existing fields.
    """
    provider = _provider(name)
    if not provider:
        return False, "backend does not support native"
    if cfg.native.get(provider, "auto") == "off":
        return False, f"native.{provider}=off"
    if _caller(os.environ) != provider:
        return False, "caller provider unknown, ambiguous or different"
    options = cfg.options(name)
    try:
        same_account = _same_account(provider, options, os.environ)
    except (OSError, RuntimeError, ValueError):
        return False, "caller account path cannot be resolved"
    if not same_account:
        return False, "caller account differs from selected backend"
    if provider == "claude":
        settings, reason = _agent_settings(PLUGIN_DIR)
        if reason:
            return False, reason
        for key in FRONTMATTER_KEYS:
            if options.get(key) != settings[key]:
                return False, f"Claude hand frontmatter {key} mismatch"
    return True, ("native eligible; caller must verify native tool capability and "
                  "select pick model/effort for Codex")
