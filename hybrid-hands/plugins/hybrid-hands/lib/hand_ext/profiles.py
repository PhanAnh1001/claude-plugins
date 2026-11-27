"""Repo profile → role table → (provider, account, model, effort), with validation.

Pure data layer: callers pass the effective config dict (``shared_config.load_config``).
Overrides live at ``profiles.<profile>.<role>`` (tiered roles: ``profiles.<p>.collect.1``)
and merge plugin default → global → repo through the shared config machinery.
"""
from __future__ import annotations

import copy
from typing import Optional

from hand_ext.constants import (MODEL_CAPABILITIES, PROFILE_ALIASES, PROFILE_KEY, PROFILE_NAMES,
                                PROFILE_OVERRIDES_KEY, PROVIDER_EFFORTS)

SPEC_FIELDS = ("provider", "account", "model", "effort")
TIERED_ROLES = ("collect", "chrome")
PLAIN_ROLES = ("super", "brain", "code")
TIERS = (1, 2)
DEFAULT_TIER = 1
# Provider → ext_hand registry holding its account slots.
ACCOUNT_REGISTRY = {"claude": "claude_accounts", "codex": "gpt_accounts"}


def _cell(provider: str, account: str, model: str, effort: str) -> dict:
    return {"provider": provider, "account": account, "model": model, "effort": effort}


# Model GPT do người dùng chốt 16/11/2026: sol cho brain/code, terra low cho cả hai bậc thu thập.
_SOL_LOW = _cell("codex", "v1", "gpt-6.1-sol", "low")
_TERRA_LOW = _cell("codex", "v1", "gpt-6.1-terra", "low")
_GPT_MONO = {
    "brain": _cell("codex", "v1", "gpt-6.1-sol", "high"),
    "code": _SOL_LOW,
    "collect": {"1": _TERRA_LOW, "2": _TERRA_LOW},
    "chrome": {"1": _cell("claude", "v2", "claude-sonnet-5-5", "low"),
               "2": _cell("claude", "v2", "claude-sonnet-5-5", "medium")},
}


def _claude_mono(account: str) -> dict:
    """Mọi vai Claude trên một tài khoản: opus cho brain/code, sonnet cho hai bậc thu thập."""
    low = _cell("claude", account, "claude-sonnet-5-5", "low")
    medium = _cell("claude", account, "claude-sonnet-5-5", "medium")
    return {
        "brain": _cell("claude", account, "claude-opus-5-5", "high"),
        "code": _cell("claude", account, "claude-opus-5-5", "low"),
        "collect": {"1": low, "2": medium},
        "chrome": {"1": dict(low), "2": dict(medium)},
    }


CLAUDE_MONO = "claude-mono"
CLAUDE_MONO_ACCOUNTS = {"v1": CLAUDE_MONO, "v2": "claude-mono-v2"}
DEFAULT_PROFILES = {
    CLAUDE_MONO: _claude_mono("v1"),
    "claude-mono-v2": _claude_mono("v2"),
    "gpt-mono": _GPT_MONO,
    "hybrid": {**_GPT_MONO, "super": _cell("claude", "v2", "claude-opus-5-5", "high")},
}


class ProfileError(ValueError):
    """Missing/unknown profile or an invalid role cell; message names the config key."""


SPELLINGS = "claude-mono [v1|v2], claude-mono-v1, claude-mono-v2, gpt-mono, hybrid"


def normalize_profile(name: str, account: Optional[str] = None) -> str:
    """Canonical profile name from `claude-mono v2`, `claude-mono-v1`, `hybrid`, ...; else ProfileError."""
    parts = str(name or "").split()
    if account is not None:
        parts.append(account)
    base = PROFILE_ALIASES.get(parts[0], parts[0]) if parts else ""
    if len(parts) == 1 and base in PROFILE_NAMES:
        return base
    if len(parts) == 2 and parts[0] == CLAUDE_MONO and parts[1] in CLAUDE_MONO_ACCOUNTS:
        return CLAUDE_MONO_ACCOUNTS[parts[1]]
    raise ProfileError(f"Profile {' '.join(parts)!r} không hợp lệ; viết một trong: {SPELLINGS} "
                       f"(v1|v2 chỉ đi sau claude-mono).")


def active_profile(cfg: dict) -> str:
    name = cfg.get(PROFILE_KEY)
    name = PROFILE_ALIASES.get(name, name) if isinstance(name, str) else name
    if name in PROFILE_NAMES:
        return name
    state = "chưa đặt" if name is None else f"không hợp lệ ({name!r})"
    raise ProfileError(f"Khoá `{PROFILE_KEY}` {state}; chọn một trong {', '.join(PROFILE_NAMES)} "
                       f"bằng `hand-ext profile set <tên>`.")


def _merged_table(cfg: dict, profile: str) -> dict:
    table = copy.deepcopy(DEFAULT_PROFILES[profile])
    overrides = (cfg.get(PROFILE_OVERRIDES_KEY) or {}).get(profile) or {}
    for role, value in overrides.items():
        if role in TIERED_ROLES and isinstance(value, dict):
            for tier, cell in value.items():
                table.setdefault(role, {}).setdefault(str(tier), {}).update(cell or {})
        elif isinstance(value, dict):
            table.setdefault(role, {}).update(value)
    return table


def _validate_cell(cfg: dict, cell: dict, key: str) -> None:
    missing = [f for f in SPEC_FIELDS if not isinstance(cell.get(f), str) or not cell[f]]
    if missing:
        raise ProfileError(f"`{key}` thiếu {', '.join(missing)}")
    provider, account, model, effort = (cell[f] for f in SPEC_FIELDS)
    if provider not in ACCOUNT_REGISTRY:
        raise ProfileError(f"`{key}.provider` = {provider!r} không hợp lệ ({', '.join(ACCOUNT_REGISTRY)})")
    if model not in MODEL_CAPABILITIES[provider]:
        raise ProfileError(f"`{key}.model` = {model!r} không thuộc provider {provider}")
    if effort not in PROVIDER_EFFORTS[provider]:
        raise ProfileError(f"`{key}.effort` = {effort!r} không hợp lệ cho {provider}")
    registry = ACCOUNT_REGISTRY[provider]
    if account not in (cfg.get("ext_hand") or {}).get(registry, {}):
        raise ProfileError(f"`{key}.account` = {account!r} không có trong ext_hand.{registry}")
    from usage_pricing import model_price
    if model_price(model) is None:
        raise ProfileError(f"`{key}.model` = {model!r} không có giá trong file giá canonical")


def _role_key(profile: str, role: str, tier: Optional[int]) -> str:
    key = f"{PROFILE_OVERRIDES_KEY}.{profile}.{role}"
    return f"{key}.{tier}" if tier is not None else key


def role_spec(cfg: dict, role: str, tier: Optional[int] = None) -> dict:
    profile = active_profile(cfg)
    if role in TIERED_ROLES:
        tier = DEFAULT_TIER if tier is None else tier
        if tier not in TIERS:
            raise ProfileError(f"Vai {role} chỉ có bậc {TIERS}, nhận {tier!r}")
    elif role in PLAIN_ROLES:
        if tier is not None:
            raise ProfileError(f"Vai {role} không có bậc")
    else:
        raise ProfileError(f"Vai {role!r} không hợp lệ ({', '.join(PLAIN_ROLES + TIERED_ROLES)})")
    table = _merged_table(cfg, profile)
    cell = table.get(role)
    if cell is not None and tier is not None:
        cell = cell.get(str(tier))
    key = _role_key(profile, role, tier)
    if cell is None:
        raise ProfileError(f"Profile {profile} không có vai {role} (`{key}`)")
    _validate_cell(cfg, cell, key)
    return {"profile": profile, "role": role, "tier": tier,
            **{f: cell[f] for f in SPEC_FIELDS}}


def profile_table(cfg: dict) -> dict:
    """Validated effective table: {"brain": spec, "collect.1": spec, ...}."""
    profile = active_profile(cfg)
    result = {}
    for role in PLAIN_ROLES + TIERED_ROLES:
        if role not in _merged_table(cfg, profile):
            continue
        for tier in (TIERS if role in TIERED_ROLES else (None,)):
            label = role if tier is None else f"{role}.{tier}"
            result[label] = role_spec(cfg, role, tier)
    return result
