"""Per-session JSON state in <state_dir>/<NAME>.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


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
    return SessionState(**json.loads(path.read_text(encoding="utf-8")))


def load_all(state_dir: Path) -> list[SessionState]:
    if not state_dir.is_dir():
        return []
    return [SessionState(**json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(state_dir.glob("*.json"))]
