"""Value objects for Paseo agents, live Claude sessions and transcripts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Agent:
    """Only the Paseo agent fields cc-switch is allowed to read."""

    id: str
    cwd: str
    provider: str
    title: str
    last_activity: str
    last_status: str
    runtime_session: str
    runtime_model: str
    persistence_session: str
    archived: bool

    def session_id(self) -> str:
        return self.runtime_session or self.persistence_session


@dataclass
class LiveSession:
    pid: int
    session_id: str
    cwd: str
    entrypoint: str
    status: str


@dataclass
class Transcript:
    session_id: str
    path: Path
    cwd: str
    has_user: bool
    mtime: float
    title: str = ""
