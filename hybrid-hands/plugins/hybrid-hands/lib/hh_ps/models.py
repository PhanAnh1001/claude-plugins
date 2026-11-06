"""Value objects shared by the hh-ps sources and renderers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .constants import (
    PROVIDER_CLAUDE, RUN_STATE_FINISHED, RUN_STATE_LOST, RUN_STATE_RUNNING,
    RUN_STATUS_RUNNING, SUBAGENT_FINISHED, SUBAGENT_RUNNING, SUBAGENT_SILENT,
)


@dataclass(frozen=True)
class Usage:
    read: int = 0
    cache_read: int = 0
    cache_write: Optional[int] = None
    out: int = 0
    usd: Optional[float] = None


@dataclass
class Subagent:
    agent_id: str
    agent_type: str
    description: str
    finished: bool
    silent: bool
    context_tokens: Optional[int]
    duration_seconds: Optional[float]
    last_activity: Optional[float]
    usage: Optional[Usage] = None

    @property
    def state(self) -> str:
        if self.finished:
            return SUBAGENT_FINISHED
        return SUBAGENT_SILENT if self.silent else SUBAGENT_RUNNING

    @property
    def running(self) -> bool:
        return self.state == SUBAGENT_RUNNING

    @property
    def ended_at(self) -> Optional[float]:
        # The last transcript record is the best end mark a finished subagent has.
        return self.last_activity if self.finished else None


@dataclass
class HandRun:
    run_id: str
    label: str
    backend: str
    model: str
    status: str
    parent_session: Optional[str]
    tokens: Dict[str, int]
    started_at: Optional[float]
    ended_at: Optional[float]
    pid: Optional[int]
    child_pid: Optional[int]
    lost: bool

    @property
    def running(self) -> bool:
        return self.status == RUN_STATUS_RUNNING and not self.lost

    @property
    def state(self) -> str:
        if self.lost:
            return RUN_STATE_LOST
        if self.status == RUN_STATUS_RUNNING:
            return RUN_STATE_RUNNING
        return RUN_STATE_FINISHED

    @property
    def end_moment(self) -> Optional[float]:
        # A lost run without `ended` in the registry has no known end mark.
        return None if self.running else self.ended_at

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.ended_at if self.ended_at is not None else time.time()
        return max(0.0, end - self.started_at)


@dataclass
class Session:
    session_id: str
    name: str
    status: str
    cwd: str
    context_tokens: Optional[int]
    started_at: Optional[float]
    last_activity: Optional[float]
    is_main: bool
    live: bool
    project_slug: str = ""
    transcript_path: Optional[Path] = None
    token_cap: Optional[int] = None
    token_ratio: Optional[float] = None
    parent_session: Optional[str] = None
    side_name: Optional[str] = None
    provider: str = PROVIDER_CLAUDE
    pulled_in: bool = False
    ai_title: str = ""
    usage: Optional[Usage] = None
    subagents: List[Subagent] = field(default_factory=list)
    hand_runs: List[HandRun] = field(default_factory=list)

    @property
    def alive(self) -> bool:
        return self.live

    @property
    def ended_at(self) -> Optional[float]:
        return None if self.live else self.last_activity


@dataclass
class Snapshot:
    sessions: List[Session]
    orphan_runs: List[HandRun]
    since_seconds: int
    cwd: str
    all_projects: bool
    main_session_id: Optional[str]
    generated_at: float
    hidden_ended_sessions: int = 0

    @property
    def live_sessions(self) -> int:
        return sum(1 for session in self.sessions if session.live)

    @property
    def running_subagents(self) -> int:
        return sum(1 for session in self.sessions
                   for agent in session.subagents if agent.running)

    @property
    def running_hand_runs(self) -> int:
        return sum(1 for run in self.iter_runs() if run.running)

    def iter_runs(self) -> List[HandRun]:
        runs = [run for session in self.sessions for run in session.hand_runs]
        return runs + list(self.orphan_runs)

