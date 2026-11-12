"""Bounded, best-effort titles for plugin-owned Paseo side sessions."""
from __future__ import annotations

import re

from . import constants as C, state

TITLE_LIMIT = 60
ACCOUNT_LIMIT = 16
MAX_ATTEMPTS = 3
MAIN_ROLES = {"main", "main_session"}


def title(st: state.SessionState) -> str:
    """Use only the explicit CLI label, never a prompt, path or config value."""
    label = st.name
    if (not re.fullmatch(r"[\w-]+", label, re.UNICODE)
            or re.search(r"secret|token|password|credential|api.?key", label, re.I)):
        label = "side"
    kind = {"codex": "Sol", "dsh": "dsh"}.get(st.provider, "?")
    if st.provider == C.PROVIDER_CLAUDE:
        account = (st.account if len(st.account) <= ACCOUNT_LIMIT
                   and re.fullmatch(r"v[1-9][0-9]*", st.account) else "?")
        family = C.CLAUDE_MODEL_LABELS.get(st.model, "Opus").split()[0]
        kind = f"{family} {account}"
    suffix = f" · {kind} phụ"
    return label[:TITLE_LIMIT - len(suffix)] + suffix


def rename(st: state.SessionState, records: list[state.SessionState], apply: bool) -> dict:
    from . import paseo
    if (st.role in MAIN_ROLES or st.transport != C.TRANSPORT_PASEO
            or not st.paseo_agent_id or not st.paseo_workspace_id or not st.paseo_target
            or any(item.paseo_agent_id == st.paseo_agent_id and item.role in MAIN_ROLES
                   for item in records)):
        return {"warning": "NAME_OWNERSHIP_BLOCKED"}
    try:
        return paseo._call("names", {
            "agentId": st.paseo_agent_id, "expectedWorkspaceId": st.paseo_workspace_id,
            "expectedTargetKey": st.paseo_target, "title": title(st), "apply": apply,
            "workspaceOwners": paseo.workspace_owners(st, records),
            "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
        }, timeout=C.PASEO_STATUS_TIMEOUT_S)
    except paseo.PaseoError:
        return {"warning": "NAME_RENAME_FAILED"}


def retry(cfg, st: state.SessionState, *, reset: bool = False) -> None:
    """Three attempts per lifecycle epoch; successful names need no polling."""
    if st.role in MAIN_ROLES or st.transport != C.TRANSPORT_PASEO:
        return
    if reset:
        st.paseo_name_attempts = 0
        st.paseo_name_done = False
    if st.paseo_name_done or st.paseo_name_attempts >= MAX_ATTEMPTS:
        return
    st.paseo_name_attempts += 1
    try:
        records = state.load_all(cfg.state_dir)
        result = rename(st, records, True)
    except (OSError, ValueError, TypeError):
        result = {"warning": "NAME_STATE_UNAVAILABLE"}
    # A shared workspace belongs to the calling chat: its title is never ours to set.
    workspace_ok = st.paseo_workspace_shared or result.get("workspaceNamed") is True
    st.paseo_name_done = result.get("agentNamed") is True and workspace_ok
    if not st.paseo_name_done:
        warning = result.get("warning", "NAME_RENAME_PENDING")
        if st.paseo_workspace_shared and warning == "NAME_WORKSPACE_BLOCKED":
            warning = "NAME_RENAME_FAILED"
        print(f"side-session: warning: {warning}")
    try:
        state.save(cfg.state_dir, st)
    except OSError:
        print("side-session: warning: NAME_STATE_WRITE_FAILED")


def tidy(cfg, args, records: list[state.SessionState]) -> int:
    failed = False
    for st in records:
        if args.name and st.name != args.name:
            continue
        if st.transport != C.TRANSPORT_PASEO:
            continue
        result = rename(st, records, args.apply)
        warning = result.get("warning", "")
        failed |= bool(warning)
        print(f"agent={st.paseo_agent_id} workspace={st.paseo_workspace_id} "
              f"title={title(st)} {'apply' if args.apply else 'dry-run'} "
              f"agentEligible={result.get('agentEligible', False)} "
              f"workspaceEligible={result.get('workspaceEligible', False)} {warning}")
    return int(failed)
