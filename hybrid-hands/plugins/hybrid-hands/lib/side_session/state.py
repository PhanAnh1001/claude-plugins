"""Per-session JSON state in <state_dir>/<NAME>.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import constants as C


@dataclass
class SessionState:
    name: str
    uuid: str
    provider: str
    dir: str
    screen: str
    watch_screen: str
    max_tokens: int
    started: float
    status: str
    handoff: str
    tokens_used: int = 0
    worktree: bool = False
    # Phiên brain đã mở phiên phụ này (CLAUDE_CODE_SESSION_ID lúc `start`); "" = không rõ.
    parent_session: str = ""
    chrome: bool = False
    budget_exempt: bool = False
    # Rollout Codex đã ghim (đường tuyệt đối); "" = chưa tìm được, không đoán.
    codex_rollout: str = ""
    # "screen" (mặc định, state cũ) hoặc "paseo" (agent do daemon Paseo sở hữu).
    transport: str = C.TRANSPORT_SCREEN
    paseo_agent_id: str = ""
    paseo_workspace_id: str = ""
    # Khoá endpoint đã lưu (home path hoặc hash host); "" = state cũ/không rõ.
    paseo_target: str = ""
    # Thread Codex lấy từ persistence/runtime của Paseo; "" = chưa có.
    codex_thread_id: str = ""
    role: str = ""
    paseo_workspace_archived: bool = False
    account: str = "v1"
    claude_config_dir: str = ""
    model: str = ""
    effort: str = ""
    # Workspace đã được side-session mở lại sau khi agent unarchive: watch/ls kiểm lại agent archive.
    paseo_revived: bool = False
    native_session_id: str = ""
    paseo_send_pending: bool = False


def _from_dict(raw: dict) -> "SessionState":
    known = {f.name for f in fields(SessionState)}
    return SessionState(**{k: v for k, v in raw.items() if k in known})


def state_path(state_dir: Path, name: str) -> Path:
    return state_dir / f"{name}.json"


def save(state_dir: Path, st: SessionState) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_path(state_dir, st.name)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(st), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load(state_dir: Path, name: str) -> SessionState:
    path = state_path(state_dir, name)
    if not path.is_file():
        raise SystemExit(f"side-session: no session named {name!r} ({path})")
    return _from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_all(state_dir: Path) -> list[SessionState]:
    if not state_dir.is_dir():
        return []
    return [_from_dict(json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(state_dir.glob("*.json"))]
