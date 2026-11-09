"""Resolve the current Claude account to an operator-managed Paseo provider."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from shared_config import GlobalConfigError, load_config

from .errors import CcSwitchError
from .models import Agent

PROVIDER_KEY = "paseo.claude_providers"


def _error(account: str, detail: str) -> CcSwitchError:
    return CcSwitchError(
        f"Account Claude {account or '?'}: {detail}. Kiểm tra {PROVIDER_KEY}; "
        "operator cần khai báo provider Claude có env CLAUDE_CONFIG_DIR "
        "tương ứng trong cấu hình Paseo.")


def _account_path(raw: str, root: Path) -> Path:
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def preflight_provider(root: Path, agents: Sequence[Agent] = ()) -> str:
    """Fail before import/reload (and before --self closes the terminal)."""
    try:
        config = load_config(known_root=root).effective
    except (GlobalConfigError, ValueError) as exc:
        raise _error("", str(exc)) from exc
    current = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    try:
        current_path = _account_path(current, root)
        accounts = config["ext_hand"]["claude_accounts"]
        matches = [name for name, entry in accounts.items()
                   if isinstance(entry, dict)
                   and isinstance(entry.get("config_dir"), str)
                   and entry["config_dir"].strip()
                   and _account_path(entry["config_dir"], root) == current_path]
    except (OSError, RuntimeError) as exc:
        raise _error("", "không phân giải được config_dir") from exc
    if len(matches) != 1:
        raise _error(", ".join(matches), "config_dir không khớp duy nhất một account")
    account = matches[0]
    providers = config.get("paseo", {}).get("claude_providers")
    provider = providers.get(account) if isinstance(providers, dict) else None
    if not isinstance(provider, str) or not provider.strip():
        raise _error(account, "thiếu provider hợp lệ")
    provider = provider.strip()
    if any(agent.provider != provider for agent in agents):
        raise _error(account, "agent cùng session có provider khác mapping; không reload")
    return provider
