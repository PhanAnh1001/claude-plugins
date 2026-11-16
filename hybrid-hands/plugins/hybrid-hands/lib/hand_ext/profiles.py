"""Repo profile → role table → (provider, account, model, effort), with validation.

Pure data layer: callers pass the effective config dict (``shared_config.load_config``).
Overrides live at ``profiles.<profile>.<role>`` (tiered roles: ``profiles.<p>.collect.1``)
and merge plugin default → global → repo through the shared config machinery.
"""
from __future__ import annotations

import copy
from typing import Optional

from hand_ext.constants import (MODEL_CAPABILITIES, PROFILE_KEY, PROFILE_NAMES,
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


_SONNET_LOW = _cell("claude", "v1", "claude-sonnet-5-5", "low")
_SONNET_MEDIUM = _cell("claude", "v1", "claude-sonnet-5-5", "medium")
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
DEFAULT_PROFILES = {
    "claude-mono": {
        "brain": _cell("claude", "v1", "claude-opus-5-5", "high"),
        "code": _cell("claude", "v1", "claude-opus-5-5", "low"),
        "collect": {"1": _SONNET_LOW, "2": _SONNET_MEDIUM},
        "chrome": {"1": _SONNET_LOW, "2": _SONNET_MEDIUM},
    },
    "gpt-mono": _GPT_MONO,
    "hybrid": {**_GPT_MONO, "super": _cell("claude", "v2", "claude-opus-5-5", "high")},
}


class ProfileError(ValueError):
    """Missing/unknown profile or an invalid role cell; message names the config key."""


def active_profile(cfg: dict) -> str:
    name = cfg.get(PROFILE_KEY)
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
