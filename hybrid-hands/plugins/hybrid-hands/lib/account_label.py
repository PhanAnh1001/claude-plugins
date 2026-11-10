"""One display label per account: ``{provider} {slot} {plan} {name}``.

Config wins (``ext_hand.claude_accounts.vN.plan|name``, ``ext_hand.gpt_accounts.vN``);
a missing plan falls back to a caller-detected plan, a missing Claude name to the
local part of ``oauthAccount.emailAddress`` in ``<config_dir>/.claude.json``. GPT has
no safe email source in this plugin, so its name stays unknown unless configured.
Only the local part is ever returned, never the full address.
"""
from __future__ import annotations

import json
import os
import string
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

UNKNOWN = "?"
PROVIDER_CLAUDE = "claude"
PROVIDER_GPT = "gpt"
DEFAULT_LABEL_FORMAT = "{provider} {slot} {plan} {name}"
PLACEHOLDERS = frozenset(("provider", "slot", "plan", "name"))
CLAUDE_STATE_FILE = ".claude.json"
DEFAULT_GPT_SLOT = "v1"
# Test-only switch: never read real account files (email/plan) while testing.
OFFLINE_ENV = "HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"
GPT_SESSIONS_DIR = "sessions"
GPT_ROLLOUT_GLOB = "rollout-*.jsonl"
PLAN_TYPE_KEY = "plan_type"
# Only the tail of the newest rollout is scanned: rate_limits repeat on every token event.
ROLLOUT_TAIL_BYTES = 256 * 1024
_warned: set[str] = set()


def _get(cfg: Any, key: str, default: Any) -> Any:
    if isinstance(cfg, Mapping):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def label_format(cfg: Any) -> str:
    """Validated format; an invalid one warns once (without echoing it) and falls back."""
    fmt = _get(cfg, "account_label_format", DEFAULT_LABEL_FORMAT)
    try:
        fields = {name for _, name, spec, conv in string.Formatter().parse(fmt) if name is not None}
        if isinstance(fmt, str) and fields <= PLACEHOLDERS:
            return fmt
    except (ValueError, TypeError):
        pass
    if "format" not in _warned:
        _warned.add("format")
        print("warning: ext_hand.account_label_format không hợp lệ; dùng mặc định", file=sys.stderr)
    return DEFAULT_LABEL_FORMAT


@lru_cache(maxsize=None)
def claude_email_name(config_dir: str) -> str:
    """Local part of the Claude account email, read from just that one key."""
    path = Path(os.path.expanduser(config_dir)) / CLAUDE_STATE_FILE
    try:
        email = json.loads(path.read_text(encoding="utf-8"))["oauthAccount"]["emailAddress"]
    except (OSError, ValueError, KeyError, TypeError):
        return UNKNOWN
    if not isinstance(email, str) or "@" not in email or not email.split("@", 1)[0].strip():
        return UNKNOWN
    return email.split("@", 1)[0].strip()


def _offline() -> bool:
    return os.environ.get(OFFLINE_ENV) == "1"


@lru_cache(maxsize=None)
def gpt_detected_plan(home: str) -> Optional[str]:
    """``rate_limits.plan_type`` from the newest local rollout; metadata only, no auth."""
    root = Path(os.path.expanduser(home)) / GPT_SESSIONS_DIR
    try:
        newest = max(root.rglob(GPT_ROLLOUT_GLOB), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            return None
        with newest.open("rb") as stream:
            stream.seek(max(0, newest.stat().st_size - ROLLOUT_TAIL_BYTES))
            lines = stream.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        if PLAN_TYPE_KEY not in raw:
            continue
        try:
            limits = (json.loads(raw).get("payload") or {}).get("rate_limits") or {}
        except (ValueError, AttributeError):
            continue
        plan = limits.get(PLAN_TYPE_KEY) if isinstance(limits, dict) else None
        if isinstance(plan, str) and plan.strip():
            return plan.strip().capitalize()
    return None


def _text(value: Any) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


def account_label(provider: str, slot: str, cfg: Any, *, detected_plan: Optional[str] = None) -> str:
    registry = _get(cfg, "claude_accounts" if provider == PROVIDER_CLAUDE else "gpt_accounts", {}) or {}
    options = registry.get(slot, {}) if isinstance(registry, Mapping) else {}
    options = options if isinstance(options, Mapping) else {}
    plan = _text(options.get("plan")) or _text(detected_plan)
    if plan is None and provider == PROVIDER_GPT and _text(options.get("home")) and not _offline():
        plan = gpt_detected_plan(options["home"])
    plan = plan or UNKNOWN
    name = _text(options.get("name"))
    if name is None and provider == PROVIDER_CLAUDE and _text(options.get("config_dir")) and not _offline():
        name = claude_email_name(options["config_dir"])
    return label_format(cfg).format(provider=provider, slot=slot or UNKNOWN,
                                    plan=plan, name=name or UNKNOWN).strip()


def account_choices(cfg: Any, selected_backend: str = "") -> list[dict]:
    """Numbered Claude then GPT accounts for pickers (``parallel-subagents accounts``)."""
    rows = []
    for provider, key, prefix in ((PROVIDER_CLAUDE, "claude_accounts", "claude-"),
                                  (PROVIDER_GPT, "gpt_accounts", None)):
        registry = _get(cfg, key, {}) or {}
        for slot in sorted(registry, key=lambda s: int(s[1:]) if s[1:].isdigit() else 0):
            backend = prefix + slot if prefix else "codex"
            rows.append({"index": len(rows) + 1, "provider": provider, "slot": slot,
                         "backend": backend, "label": account_label(provider, slot, cfg),
                         "selected": backend == selected_backend})
    return rows


def backend_account_label(backend: str, cfg: Any, *, detected_plan: Optional[str] = None) -> Optional[str]:
    """Label for a backend name (``claude-vN``, aliases, ``codex``); None for others (dsh)."""
    slot = {"claude-main": "v1", "claude": "v2"}.get(backend)
    if slot is None and backend.startswith("claude-v"):
        slot = backend[len("claude-"):]
    if slot is not None:
        return account_label(PROVIDER_CLAUDE, slot, cfg, detected_plan=detected_plan)
    if backend == "codex":
        return account_label(PROVIDER_GPT, DEFAULT_GPT_SLOT, cfg, detected_plan=detected_plan)
    return None
