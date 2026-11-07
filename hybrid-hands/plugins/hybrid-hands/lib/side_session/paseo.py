"""Paseo daemon transport for side-session Codex sessions.

The installed CLI's own `dist/utils/client.js` and `dist/utils/daemon-target.js`
(compatibility: @getpaseo/cli 0.15.0) are loaded by `paseo_bridge.mjs`. Paseo keeps
ownership of credentials and target discovery; this module only resolves the package
from PATH and exchanges one JSON request/response per call without a shell.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import codex_trust
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
    for key in C.PASEO_INHERITED_ENVS:
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
        raise PaseoError("NODE_NOT_FOUND")
    root = cli_package_root()
    if root is None:
        raise PaseoError("PASEO_CLI_NOT_FOUND")
    try:
        proc = subprocess.run(
            [node, str(BRIDGE), str(root)],
            input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True,
            timeout=timeout, env=clean_env())
    except subprocess.TimeoutExpired as exc:
        raise PaseoError("PASEO_TIMEOUT") from exc
    except OSError as exc:
        raise PaseoError("PASEO_BRIDGE_FAILED") from exc
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


def start_agent(*, workdir: str, name: str, model: str, effort: str,
                initial_prompt: str, codex_home: Path,
                writable_roots: list[str], target_key: str) -> dict:
    """Create the directory workspace and `codex-hand` agent in one bridge call."""
    provider_options = {
        "approval_policy": C.CODEX_APPROVAL,
        "sandbox_mode": C.CODEX_SANDBOX,
        "sandbox_workspace_write": {
            "network_access": True,
            "writable_roots": list(writable_roots),
        },
    }
    return _call("start", {
        "source": {"kind": "directory", "path": workdir},
        "workdir": workdir,
        "provider": C.PASEO_PROVIDER,
        "title": name,
        "model": model,
        "effort": effort,
        "initialPrompt": initial_prompt,
        "env": {"CODEX_HOME": str(codex_home)},
        "providerOptions": provider_options,
        "expectedTargetKey": target_key,
        "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS,
    }, timeout=C.PASEO_START_TIMEOUT_S)


def status(agent_id: str, target_key: str) -> dict:
    return _call("status", {"agentId": agent_id, "expectedTargetKey": target_key,
                            "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS},
                 timeout=C.PASEO_STATUS_TIMEOUT_S)


def stop_agent(agent_id: str, target_key: str) -> dict:
    return _call("stop", {"agentId": agent_id, "expectedTargetKey": target_key,
                          "timeoutMs": C.PASEO_CONNECT_TIMEOUT_MS},
                 timeout=C.PASEO_STOP_TIMEOUT_S)


def plan(cfg: SideConfig, a) -> dict | None:
    """Read-only daemon check before any worktree; None means the screen fallback.

    A non-empty codex_profile is only unsupported once the daemon is known to be
    ready: falling back to screen then would silently lose the phone-controlled
    agent. With no daemon (or in dry-run) the plan stays the old screen profile.
    """
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


def start_session(cfg: SideConfig, a, st: state.SessionState, workdir: str,
                  full_prompt: str, target: str) -> int:
    """Create worktree then workspace/agent; any failure after the ready check is final."""
    cfg.handoff_dir.mkdir(parents=True, exist_ok=True)
    if a.worktree:
        if subprocess.run(K.worktree_cmd(cfg, st.name, a.base or C.DEFAULT_BASE)).returncode != 0:
            print("side-session: failed: git worktree add")
            return 1
    st.transport = C.TRANSPORT_PASEO
    st.screen = ""
    st.paseo_target = target
    try:
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
            workdir=workdir, name=st.name, model=a.model or cfg.codex_model,
            effort=a.effort or cfg.codex_effort, initial_prompt=full_prompt,
            codex_home=cfg.codex_home, writable_roots=K.codex_writable_roots(cfg, workdir),
            target_key=st.paseo_target)
    except PaseoError as exc:
        st.paseo_agent_id = str(exc.data.get("agentId") or "")
        st.paseo_workspace_id = str(exc.data.get("workspaceId") or "")
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
    st.paseo_target = str(result.get("targetKey") or st.paseo_target)
    st.codex_thread_id = str(result.get("threadId") or "")
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
    if subprocess.run(K.watch_cmd(cfg, st.name)).returncode != 0:
        print("side-session: warning: watchdog failed to start")
    print(f"started {st.name} (Paseo agent {st.paseo_agent_id}), uuid {st.uuid}, "
          f"context {C.CODEX_AUTO_COMPACT_TOKEN_LIMIT} (tự nén); "
          "mở app Paseo hoặc `paseo attach`")
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
    if thread and not st.codex_thread_id:
        st.codex_thread_id = thread
        state.save(cfg.state_dir, st)
    raw = str(result.get("status") or "")
    if not active:
        if raw in C.PASEO_AGENT_ALIVE or raw == C.PASEO_AGENT_IDLE:
            return "alive"
        return "dead" if raw in C.PASEO_AGENT_DEAD else "unknown"
    if raw in C.PASEO_AGENT_ALIVE:
        st.status = C.STATUS_RUNNING
    elif raw == C.PASEO_AGENT_IDLE:
        st.status = C.STATUS_IDLE
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
