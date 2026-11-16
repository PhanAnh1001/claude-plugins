"""Default provider/account/model/effort for `side-session start` from the repo profile role."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from hand_ext.profiles import ProfileError, active_profile, role_spec

from . import constants as C

ROLE_SUPER = "super"
ROLE_BRAIN = "brain"
# Only the hybrid profile has a dedicated main-session role; mono profiles reuse brain.
PROFILE_HYBRID = "hybrid"
FIELDS = ("provider", "account", "model", "effort")

__all__ = ["ProfileError", "start_defaults", "load_effective", "role_for"]


def role_for(effective_cfg: dict, is_main: bool) -> str:
    if is_main and active_profile(effective_cfg) == PROFILE_HYBRID:
        return ROLE_SUPER
    return ROLE_BRAIN


def start_defaults(effective_cfg: dict, is_main: bool, flags: dict) -> dict:
    """CLI flags win; the role cell fills the rest only when the provider matches the cell.

    Returns {provider, account, model, effort}; a None value means "use the provider's
    legacy default". Account is only filled for claude (side-session accounts are Claude's).
    Raises ProfileError when the profile is missing/unknown or the cell is invalid.
    """
    cell = role_spec(effective_cfg, role_for(effective_cfg, is_main))
    provider = flags.get("provider") or cell["provider"]
    out = {f: flags.get(f) for f in FIELDS}
    out["provider"] = provider
    if provider != cell["provider"]:
        return out
    for field in ("model", "effort"):
        out[field] = out[field] or cell[field]
    if provider == C.PROVIDER_CLAUDE:
        out["account"] = out["account"] or cell["account"]
    return out


def load_effective(repo: Path) -> dict:
    from shared_config import load_config as load_shared
    return load_shared(known_root=repo).effective


def resolve(repo: Path, is_main: bool, flags: dict) -> Optional[dict]:
    """start_defaults plus "role" (super/brain) for the HYBRID_HANDS_ROLE marker."""
    effective = load_effective(repo)
    return {**start_defaults(effective, is_main, flags), "role": role_for(effective, is_main)}
