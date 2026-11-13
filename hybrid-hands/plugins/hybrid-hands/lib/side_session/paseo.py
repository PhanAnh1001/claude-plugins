"""Paseo daemon transport for side-session Codex sessions.

The installed CLI's own `dist/utils/client.js` and `dist/utils/daemon-target.js`
(compatibility: @getpaseo/cli 0.15.0) are loaded by `paseo_bridge.mjs`. Paseo keeps
ownership of credentials and target discovery; this module only resolves the package
from PATH and exchanges one JSON request/response per call without a shell.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from . import codex_trust, names
from .claude_options import process_options
from . import commands as K
from . import constants as C
from . import state
from .config import SideConfig

BRIDGE = Path(__file__).with_name(C.PASEO_BRIDGE_RELPATH)
CLIENT_RELPATH = Path("dist") / "utils" / "client.js"
TARGET_RELPATH = Path("dist") / "utils" / "daemon-target.js"
_SAFE_CODE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class PaseoError(RuntimeError):
    """A bridge/daemon failure reduced to a safe code plus optional ids."""

    def __init__(self, code: str, data: dict | None = None):
        super().__init__(code)
        self.code = code
        self.data = data or {}


def clean_env() -> dict[str, str]:
    """Environment for bridge/watchdog processes, without ambient Paseo ownership."""
    env = dict(os.environ)
    for key in (*C.PASEO_INHERITED_ENVS, C.CLAUDE_AUTO_COMPACT_ENV):
        env.pop(key, None)
    return env


def disabled() -> bool:
    return bool(os.environ.get(C.PASEO_DISABLE_ENV))


def cli_package_root() -> Path | None:
    """Resolve the CLI package root from the real `paseo` binary, never a fixed NVM path."""
    found = shutil.which(C.PASEO_BIN)
    if not found:
        return None
    root = Path(os.path.realpath(found)).parent.parent
    if (root / CLIENT_RELPATH).is_file() and (root / TARGET_RELPATH).is_file():
        return root
    return None


def _safe_code(raw: object) -> str:
    code = str(raw or "")
    return code if code and set(code) <= _SAFE_CODE else "PASEO_ERROR"


def _call(command: str, payload: dict | None = None, *, timeout: float) -> dict:
    request = {"command": command, **(payload or {})}
    node = shutil.which(C.PASEO_NODE)
    if node is None:
        raise PaseoError("NODE_NOT_FOUND", {"notSent": True} if command == "send" else {})
    root = cli_package_root()
    if root is None:
        raise PaseoError("PASEO_CLI_NOT_FOUND", {"notSent": True} if command == "send" else {})
    try:
        proc = subprocess.run(
            [node, str(BRIDGE), str(root)],
            input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True,
            timeout=timeout, env=clean_env())
    except subprocess.TimeoutExpired as exc:
        raise PaseoError("PASEO_TIMEOUT") from exc
    except OSError as exc:
        raise PaseoError("PASEO_BRIDGE_FAILED", {"notSent": True} if command == "send" else {}) from exc
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    try:
        response = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError as exc:
        raise PaseoError("PASEO_BRIDGE_PROTOCOL") from exc
    data = response.get("data") if isinstance(response, dict) else {}
    # A non-zero bridge exit is a failure even if a stray `ok: true` line is printed.
    if proc.returncode != 0:
        raise PaseoError(_safe_code(response.get("code") if isinstance(response, dict)
                                    else "PASEO_BRIDGE_FAILED"),
                         data if isinstance(data, dict) else {})
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise PaseoError(_safe_code(response.get("code") if isinstance(response, dict)
                                    else "PASEO_BRIDGE_FAILED"),
                         data if isinstance(data, dict) else {})
    return response


def ready() -> dict:
    """Read-only daemon check; returns {targetKey}."""
    return _call("ready", timeout=C.PASEO_READY_TIMEOUT_S)


def _claude_launch(config_dir: str, account: str) -> tuple[dict[str, str], dict[str, str]]:
    """Primary login requires an unset config override and the default provider.

    Resolve paths just as the screen launcher does; account names alone cannot
    identify the primary login because account directories are configurable.
    """
    primary = (Path(config_dir).expanduser().resolve()
               == (Path.home() / ".claude").resolve())
    if primary:
        return {}, {}
    env = {"CLAUDE_CONFIG_DIR": config_dir}
    selection = ({"accountProvider": C.PASEO_CLAUDE_ACCOUNT_PROVIDER_PREFIX + account}
                 if account else {})
    return env, selection


def start_agent(*, workdir: str, name: str, model: str, effort: str,
                initial_prompt: str, codex_home: Path, target_key: str, hand_scope: str,
                project_root: str, provider: str = C.PROVIDER_CODEX,
                claude_config_dir: str = "", mode_id: str = "",
                claude_options: dict | None = None,
                claude_auto_compact_window: int | None = None,
                caller_agent_id: str = "", account: str = "") -> dict:
    """Create a directory workspace and the selected provider in one bridge call."""
    provider_options = {
        "approval_policy": C.CODEX_APPROVAL,
        "sandbox_mode": C.CODEX_SANDBOX,
    }
    env = {"CODEX_HOME": str(codex_home), C.HAND_SCOPE_ENV: hand_scope}
    # Codex payload keeps the old shape: Claude-only fields are added below.
    claude_only: dict = {}
    if provider == C.PROVIDER_CLAUDE:
        env, selection = _claude_launch(claude_config_dir, account)
        env[C.HAND_SCOPE_ENV] = hand_scope
        if claude_auto_compact_window is not None:
            env[C.CLAUDE_AUTO_COMPACT_ENV] = str(claude_auto_compact_window)
        provider_options = claude_options or {}
        claude_only = {"modeId": mode_id or None}
        claude_only.update(selection)
    return _call("start", {
        "source": {"kind": "directory", "path": workdir},
        "projectRoot": project_root,
        "workdir": workdir,
        "provider": "claude" if provider == C.PROVIDER_CLAUDE else C.PASEO_PROVIDER,
        "title": name,
        "model": model,
        "effort": effort,
        "initialPrompt": initial_prompt,
        "env": env,
        "providerOptions": provider_options,
        "expectedTargetKey": target_key,
        "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
        "callerAgentId": caller_agent_id or None,
        **claude_only,
    }, timeout=C.PASEO_START_TIMEOUT_S)


def status(agent_id: str, target_key: str) -> dict:
    return _call("status", {"agentId": agent_id, "expectedTargetKey": target_key,
                            "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS},
                 timeout=C.PASEO_STATUS_TIMEOUT_S)


def subagents(agent_id: str, target_key: str) -> dict:
    """Read native provider children; these are not hand-ext ledger runs."""
    return _call("subagents", {
        "agentId": agent_id,
        "expectedTargetKey": target_key,
        "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
    }, timeout=C.PASEO_STATUS_TIMEOUT_S)


def subagent_timeline(agent_id: str, subagent_id: str, target_key: str) -> dict:
    """Read a native child's timeline after the bridge verifies parent ownership."""
    return _call("subagent-timeline", {
        "agentId": agent_id,
        "subagentId": subagent_id,
        "expectedTargetKey": target_key,
        "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
    }, timeout=C.PASEO_STATUS_TIMEOUT_S)


def stop_agent(agent_id: str, target_key: str) -> dict:
    return _call("stop", {"agentId": agent_id, "expectedTargetKey": target_key,
                          "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS},
                 timeout=C.PASEO_STOP_TIMEOUT_S)


def _exact_agent(st: state.SessionState) -> dict | None:
    """Payload for an exact-agent bridge operation; None after the main/ID guards fail."""
    if st.role == "main":
        return None
    if not st.paseo_agent_id:
        return None
    if not st.paseo_workspace_id:
        return None
    return {"agentId": st.paseo_agent_id,
            "expectedWorkspaceId": st.paseo_workspace_id,
            "expectedTargetKey": st.paseo_target,
            "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
            "privateWorkspace": bool(st.role != "main" and not st.paseo_workspace_shared
                                     and Path(st.dir).is_absolute()),
            "sharedWorkspace": st.paseo_workspace_shared,
            "workdir": st.dir}


def _guard_message(st: state.SessionState) -> str:
    if st.role == "main":
        return "MAIN_ARCHIVE_FORBIDDEN"
    return "WORKSPACE_ID_UNKNOWN" if st.paseo_agent_id else "AGENT_ID_UNKNOWN"


def finish(st: state.SessionState) -> str | None:
    """Archive the exact agent and private workspace, preserving history."""
    payload = _exact_agent(st)
    if payload is None:
        return _guard_message(st)
    try:
        result = _call("finish", payload, timeout=C.PASEO_STOP_TIMEOUT_S)
        if (result.get("agentArchived") is not True
                or result.get("agentId") != st.paseo_agent_id
                or result.get("workspaceId") != st.paseo_workspace_id
                or result.get("targetKey") != st.paseo_target):
            return "AGENT_ARCHIVE_UNCONFIRMED"
    except PaseoError as exc:
        return exc.code
    return None


def agent_archive_states(candidates: list[state.SessionState]) -> dict[str, bool]:
    """Validate the snapshot and return archive states only for matching candidates."""
    targets = {st.paseo_target for st in candidates if st.paseo_target}
    if len(targets) > 1:
        raise PaseoError("TARGET_CHANGED")
    result = _call("agent-archive-states", {"expectedTargetKey": next(iter(targets), "")},
                   timeout=C.PASEO_STOP_TIMEOUT_S)
    target = result.get("targetKey")
    entries = result.get("agents")
    if not isinstance(target, str) or not target.strip() or not isinstance(entries, list):
        raise PaseoError("PASEO_BRIDGE_PROTOCOL")
    if targets and target not in targets:
        raise PaseoError("TARGET_CHANGED")
    directory = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PaseoError("PASEO_BRIDGE_PROTOCOL")
        aid, wid = entry.get("agentId"), entry.get("workspaceId")
        if not isinstance(aid, str) or not aid.strip() \
                or not isinstance(wid, str) or not wid.strip() \
                or "archivedAt" not in entry \
                or (entry["archivedAt"] is not None and not isinstance(entry["archivedAt"], str)) \
                or aid in directory:
            raise PaseoError("PASEO_BRIDGE_PROTOCOL")
        directory[aid] = entry
    archive_states = {}
    for st in candidates:
        entry = directory.get(st.paseo_agent_id)
        if entry is None or not st.paseo_workspace_id \
                or entry["workspaceId"] != st.paseo_workspace_id:
            continue
        archive_states[st.paseo_agent_id] = entry["archivedAt"] is not None
    return archive_states


def revive(st: state.SessionState) -> tuple[bool | None, str | None]:
    """Reopen the private workspace of an agent the user already unarchived.

    Returns (revived, error): the bridge reports the agent still archived as
    (False, None); every case without a confirmed mutation is (None, code).
    """
    payload = _exact_agent(st)
    if payload is None:
        return None, _guard_message(st)
    try:
        result = _call("revive", payload, timeout=C.PASEO_STOP_TIMEOUT_S)
    except PaseoError as exc:
        return None, exc.code
    revived = result.get("revived")
    if revived is True or revived is False:
        return revived, None
    return None, "PASEO_BRIDGE_PROTOCOL"


def rearchive(st: state.SessionState, owners: list[state.SessionState] | None = None) -> tuple[bool | None, str | None]:
    """Archive only the private workspace once the revived agent is archived again."""
    payload = _exact_agent(st)
    if payload is None:
        return None, _guard_message(st)
    try:
        payload["workspaceOwners"] = workspace_owners(st, [st] if owners is None else owners)
        result = _call("rearchive", payload, timeout=C.PASEO_STOP_TIMEOUT_S)
    except PaseoError as exc:
        return None, exc.code
    archived = result.get("archived")
    if archived is True or archived is False:
        return archived, None
    return None, "PASEO_BRIDGE_PROTOCOL"


def workspace_owners(st: state.SessionState, records: list[state.SessionState]) -> list[dict]:
    """Only this repo's recorded exact workspace/target identifies ownership."""
    return [{"agentId": item.paseo_agent_id, "workspaceId": item.paseo_workspace_id,
             "role": item.role, "status": item.status,
             "sendPending": item.paseo_send_pending}
            for item in records if item.paseo_workspace_id == st.paseo_workspace_id
            and item.paseo_target == st.paseo_target
            and item.transport == C.TRANSPORT_PASEO]


def tidy_workspace(st: state.SessionState, records: list[state.SessionState], apply: bool) -> dict:
    payload = {"expectedWorkspaceId": st.paseo_workspace_id,
               "expectedTargetKey": st.paseo_target, "workdir": st.dir,
               "privateWorkspace": st.role != "main" and not st.paseo_workspace_shared,
               "apply": apply,
               "workspaceOwners": workspace_owners(st, records)}
    result = _call("tidy", payload, timeout=C.PASEO_STOP_TIMEOUT_S)
    if (result.get("workspaceId") != st.paseo_workspace_id
            or result.get("targetKey") != st.paseo_target
            or result.get("eligible") is not True
            or not isinstance(result.get("archived"), bool)):
        raise PaseoError("PASEO_BRIDGE_PROTOCOL")
    return result


def plan(cfg: SideConfig, a) -> dict | None:
    """Read-only daemon check before any worktree; None means the screen fallback.

    A non-empty codex_profile is only unsupported once the daemon is known to be
    ready: falling back to screen then would silently lose the phone-controlled
    agent. With no daemon (or in dry-run) the plan stays the old screen profile.
    """
    if a.provider == C.PROVIDER_CLAUDE:
        if getattr(a, "transport", cfg.transport) == C.TRANSPORT_SCREEN:
            return None
        try:
            process_options(cfg, a.chrome)
        except ValueError as exc:
            print(exc)
            return {"error": "CLAUDE_OPTIONS_INVALID", "exit_code": C.EXIT_USAGE}
        if a.dry_run:
            return {"target": ""}
        try:
            if disabled() or cli_package_root() is None:
                raise PaseoError("PASEO_REQUIRED")
            target = str(ready().get("targetKey") or "")
            if not target:
                raise PaseoError("PASEO_REQUIRED")
            return {"target": target}
        except PaseoError as exc:
            print(f"side-session: Claude cần Paseo ({exc.code}); không fallback screen")
            return {"error": exc.code, "exit_code": 1}
    if getattr(a, "main", False):
        if a.dry_run:
            return {"target": ""}
        if disabled() or cli_package_root() is None:
            print("side-session: --main cần daemon Paseo; không fallback screen")
            return {"error": "PASEO_REQUIRED", "exit_code": 1}
        try:
            target = str(ready().get("targetKey") or "")
        except PaseoError as exc:
            print(f"side-session: --main cần daemon Paseo kết nối được ({exc.code}); không fallback screen")
            return {"error": exc.code, "exit_code": 1}
        if not target or cfg.codex_profile:
            print("side-session: --main cần endpoint Paseo và codex_profile rỗng; không fallback screen")
            return {"error": "PASEO_REQUIRED", "exit_code": 1}
        return {"target": target}
    if a.provider != C.PROVIDER_CODEX or disabled():
        return None
    if a.dry_run:
        print("# dry-run: chưa probe daemon Paseo; kế hoạch dưới là screen fallback")
        return None
    if cli_package_root() is None:
        print("side-session: không tìm thấy @getpaseo/cli đã cài; dùng screen")
        return None
    try:
        ready_result = ready()
    except PaseoError as exc:
        print(f"side-session: warning: Paseo không kết nối được ({exc.code}); dùng screen")
        return None
    target = str(ready_result.get("targetKey") or "")
    if not target:
        print("side-session: warning: Paseo không trả endpoint; dùng screen")
        return None
    if cfg.codex_profile:
        print(f"side-session: codex_profile {cfg.codex_profile!r} chưa hỗ trợ trên "
              "đường Paseo; daemon đang sẵn sàng nên không fallback screen")
        return {"error": C.PASEO_PROFILE_UNSUPPORTED}
    return {"target": target}


def _create_uncertain(exc: PaseoError, agent_id: str) -> bool:
    """Only a definite rejection frees the slot; timeout/protocol/ids stay unknown."""
    return bool(agent_id) or exc.code not in C.PASEO_CREATE_REJECTED


def _print_unknown_guidance(st: state.SessionState) -> None:
    print(f"side-session: giữ slot và chặn tên {st.name}; kiểm app Paseo hoặc `paseo ls`.")
    if st.paseo_agent_id:
        print(f"side-session: chạy `side-session stop {st.name}` để dừng agent đã ghi nhận.")
        return
    print("side-session: chưa biết agent id; dừng mọi agent đã tạo trong app Paseo trước, "
          f"SAU ĐÓ chạy `side-session stop {st.name}` để xác nhận cleanup và giải phóng slot.")


def _caller_agent_id(a, st: state.SessionState) -> str:
    """Caller selects the workspace for any role, never the new agent's parent."""
    if getattr(a, "new_workspace", False):
        return ""
    return os.environ.get(C.PASEO_CALLER_AGENT_ENV, "").strip()


def start_session(cfg: SideConfig, a, st: state.SessionState, workdir: str,
                  full_prompt: str, target: str) -> int:
    """Create worktree then workspace/agent; any failure after the ready check is final."""
    if a.dry_run:
        print(f"# dry-run: Paseo role={st.role or 'side'} dir={workdir} "
              f"model={a.model or cfg.codex_model} effort={a.effort or cfg.codex_effort}")
        selection: dict[str, str] = {}
        if st.provider == C.PROVIDER_CLAUDE:
            env, selection = _claude_launch(st.claude_config_dir, st.account)
        else:
            env = {"CODEX_HOME": str(cfg.codex_home)}
        env[C.HAND_SCOPE_ENV] = st.uuid
        if st.claude_auto_compact_window is not None:
            env[C.CLAUDE_AUTO_COMPACT_ENV] = str(st.claude_auto_compact_window)
        options = process_options(cfg, st.chrome) if st.provider == C.PROVIDER_CLAUDE else {}
        # Dry-run never probes the daemon: show the account provider tried first.
        print(json.dumps({"provider": "claude" if st.provider == C.PROVIDER_CLAUDE
                          else C.PASEO_PROVIDER, "env": env,
                          "model": st.model, "thinkingOptionId": st.effort,
                          **({"accountProvider": selection["accountProvider"]
                              + " (nếu daemon có, không thì claude)"} if selection else {}),
                          **({"modeId": options["mode_id"] or None,
                              "providerOptions": options["claude_options"]} if options else {})}, ensure_ascii=False))
        if a.worktree:
            for step in K.worktree_steps(cfg, st.name, a.base or C.DEFAULT_BASE,
                                         sparse=not getattr(a, "no_sparse", False)):
                print(shlex.join(step.argv))
        print(full_prompt)
        return 0
    if st.role != "main":
        cfg.handoff_dir.mkdir(parents=True, exist_ok=True)
    if a.worktree:
        from . import checkout
        checkout.intent(cfg, st)
        steps = K.worktree_steps(cfg, st.name, a.base or C.DEFAULT_BASE,
                                 sparse=not getattr(a, "no_sparse", False))
        if K.run_worktree_steps(steps) != 0:
            return 1
        checkout.created(cfg, st)
    st.transport = C.TRANSPORT_PASEO
    st.screen = ""
    st.paseo_target = target
    try:
        if st.provider == C.PROVIDER_CODEX:
            codex_trust.ensure_codex_compact_limit(
                cfg.codex_home, C.CODEX_AUTO_COMPACT_TOKEN_LIMIT)
    except (codex_trust.ConfigWriteError, OSError):
        st.status = C.STATUS_ERROR
        state.save(cfg.state_dir, st)
        print("side-session: CONFIG_WRITE_FAILED (native Codex app-server); "
              "không fallback screen")
        return 1
    try:
        result = start_agent(
            workdir=workdir, name=st.name if st.role in names.MAIN_ROLES else names.title(st),
            model=a.model or cfg.codex_model,
            effort=a.effort or cfg.codex_effort, initial_prompt=full_prompt,
            codex_home=cfg.codex_home, hand_scope=st.uuid,
            project_root=str(cfg.repo),
            target_key=st.paseo_target,
            caller_agent_id=_caller_agent_id(a, st),
            **({"provider": st.provider, "claude_config_dir": st.claude_config_dir,
                "account": st.account,
                "claude_auto_compact_window": st.claude_auto_compact_window,
                **process_options(cfg, st.chrome)} if st.provider == C.PROVIDER_CLAUDE else {}))
    except PaseoError as exc:
        st.paseo_agent_id = str(exc.data.get("agentId") or "")
        st.paseo_workspace_id = str(exc.data.get("workspaceId") or "")
        st.paseo_workspace_shared = exc.data.get("workspaceShared") is True
        if _create_uncertain(exc, st.paseo_agent_id):
            st.status = C.STATUS_UNKNOWN
            state.save(cfg.state_dir, st)
            print(f"side-session: tạo agent Paseo chưa rõ kết quả ({exc.code}); "
                  "không fallback screen")
            if st.paseo_agent_id:
                print(f"side-session: đã ghi agent id {st.paseo_agent_id} vào state")
            _print_unknown_guidance(st)
        else:
            st.status = C.STATUS_ERROR
            state.save(cfg.state_dir, st)
            print(f"side-session: tạo agent Paseo lỗi ({exc.code}); không fallback screen")
        return 1
    st.paseo_agent_id = str(result.get("agentId") or "")
    st.paseo_workspace_id = str(result.get("workspaceId") or "")
    st.paseo_workspace_shared = result.get("workspaceShared") is True
    st.paseo_target = str(result.get("targetKey") or st.paseo_target)
    capture_native_id(st, str(result.get("threadId") or ""))
    if not st.paseo_agent_id:
        st.status = C.STATUS_UNKNOWN
        state.save(cfg.state_dir, st)
        print("side-session: Paseo không trả agent id; không fallback screen")
        _print_unknown_guidance(st)
        return 1
    st.status = C.STATUS_RUNNING
    # Save once, before the watchdog can legitimately write done/tokens. No second
    # save here may overwrite what the watcher already persisted.
    state.save(cfg.state_dir, st)
    names.retry(cfg, st)
    if st.role != "main" and subprocess.run(K.watch_cmd(cfg, st.name)).returncode != 0:
        print("side-session: warning: watchdog failed to start")
    usage = (f"context {C.CODEX_AUTO_COMPACT_TOKEN_LIMIT} (tự nén)"
             if st.provider == C.PROVIDER_CODEX else (f"context {st.claude_auto_compact_window} (tự nén)"
                   if st.claude_auto_compact_window is not None else f"cap {st.max_tokens}"))
    print(f"started {st.name} (Paseo agent {st.paseo_agent_id}), uuid {st.uuid}, "
          f"{usage}; mở app Paseo hoặc `paseo attach`")
    return 0


def refresh(cfg: SideConfig, st: state.SessionState) -> str:
    """Refresh live/session metadata; never resurrect a terminal side-session."""
    active = st.status in C.ACTIVE_STATUSES
    if not st.paseo_agent_id:
        return "unknown" if active else "dead"
    try:
        result = status(st.paseo_agent_id, st.paseo_target)
    except PaseoError as exc:
        if exc.code == C.PASEO_AGENT_NOT_FOUND:
            if active:
                st.status = C.STATUS_DEAD
                state.save(cfg.state_dir, st)
            return "dead"
        return "unknown"
    thread = str(result.get("threadId") or "")
    if thread:
        capture_native_id(st, thread)
        state.save(cfg.state_dir, st)
    raw = str(result.get("status") or "")
    if not active:
        if raw in C.PASEO_AGENT_ALIVE or raw == C.PASEO_AGENT_IDLE:
            return "alive"
        return "dead" if raw in C.PASEO_AGENT_DEAD else "unknown"
    if raw in C.PASEO_AGENT_ALIVE:
        st.status = C.STATUS_RUNNING
    elif raw == C.PASEO_AGENT_IDLE:
        st.status = (C.STATUS_IDLE_NO_DONE if st.provider == C.PROVIDER_CODEX and st.role != "main"
                     else C.STATUS_IDLE)
    elif raw in C.PASEO_AGENT_DEAD:
        st.status = C.STATUS_DEAD
        state.save(cfg.state_dir, st)
        return "dead"
    else:
        return "unknown"
    state.save(cfg.state_dir, st)
    return "alive"


def interrupt(st: state.SessionState) -> str | None:
    """Interrupt the exact stored agent; a missing agent is already stopped."""
    if not st.paseo_agent_id:
        return None
    try:
        stop_agent(st.paseo_agent_id, st.paseo_target)
    except PaseoError as exc:
        return None if exc.code == C.PASEO_AGENT_NOT_FOUND else exc.code
    return None


def capture_native_id(st: state.SessionState, native_id: str) -> bool:
    """Keep Claude persistence identifiers out of Codex rollout metadata.

    Returns True when this call supplied a Codex thread id that was not known yet.
    """
    if st.provider == C.PROVIDER_CLAUDE:
        st.native_session_id = native_id
        return False
    if st.codex_thread_id or not native_id:
        return False
    st.codex_thread_id = native_id
    return True


def send(st: state.SessionState, text: str, *, watch_identity: dict | None = None) -> None:
    payload = _exact_agent(st)
    if payload is None or not st.paseo_target:
        raise PaseoError("SEND_IDENTITY_UNKNOWN", {"notSent": True})
    safety = ({"watchNativeId": watch_identity["native_id"],
               "watchProvider": watch_identity["paseo_provider"]} if watch_identity else {})
    result = _call("send", {**payload, "text": text, **safety}, timeout=C.PASEO_START_TIMEOUT_S)
    if (result.get("accepted") is not True
            or result.get("agentId") != st.paseo_agent_id
            or result.get("workspaceId") != st.paseo_workspace_id
            or result.get("targetKey") != st.paseo_target):
        raise PaseoError("SEND_ACK_UNKNOWN")
