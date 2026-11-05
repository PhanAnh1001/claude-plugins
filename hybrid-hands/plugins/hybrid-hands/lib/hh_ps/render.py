"""JSON output for `hh-ps`; text rendering lives in `text_render` for size."""
from __future__ import annotations

from typing import Dict

from .constants import SCHEMA_VERSION, SUBAGENT_SILENT
from .models import HandRun, Session, Snapshot, Subagent
from .text_render import color_enabled, render_text
from .timeutil import iso_at

__all__ = ["color_enabled", "render_json", "render_text"]


def _hand_run_json(run: HandRun, now: float) -> Dict[str, object]:
    end = run.ended_at if run.ended_at is not None else now
    duration = None if run.started_at is None else max(0.0, end - run.started_at)
    return {
        "run_id": run.run_id,
        "label": run.label,
        "backend": run.backend,
        "model": run.model,
        "status": run.status,
        "state": run.state,
        "tokens": dict(run.tokens),
        "started_at": iso_at(run.started_at),
        "ended_at": iso_at(run.ended_at),
        "duration_seconds": duration,
        "parent_session": run.parent_session,
        "pid": run.pid,
        "child_pid": run.child_pid,
    }


def _subagent_json(agent: Subagent) -> Dict[str, object]:
    status = ("running" if agent.running else
              "silent" if agent.state == SUBAGENT_SILENT else "finished")
    return {
        "agent_id": agent.agent_id,
        "agent_type": agent.agent_type,
        "description": agent.description,
        "status": status,
        "context_tokens": agent.context_tokens,
        "duration_seconds": agent.duration_seconds,
    }


def _session_json(session: Session, now: float) -> Dict[str, object]:
    return {
        "session_id": session.session_id,
        "name": session.name,
        "status": session.status,
        "cwd": session.cwd,
        "context_tokens": session.context_tokens,
        "started_at": iso_at(session.started_at),
        "last_activity": iso_at(session.last_activity),
        "is_main": session.is_main,
        "live": session.live,
        "project_slug": session.project_slug,
        "transcript_path": str(session.transcript_path) if session.transcript_path else None,
        "token_cap": session.token_cap,
        "token_ratio": session.token_ratio,
        "parent_session": session.parent_session,
        "side_name": session.side_name,
        "provider": session.provider,
        "subagents": [_subagent_json(agent) for agent in session.subagents],
        "hand_runs": [_hand_run_json(run, now) for run in session.hand_runs],
    }


def render_json(snapshot: Snapshot) -> Dict[str, object]:
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": iso_at(snapshot.generated_at),
        "since_seconds": snapshot.since_seconds,
        "cwd": snapshot.cwd,
        "all_projects": snapshot.all_projects,
        "main_session_id": snapshot.main_session_id,
        "sessions": [_session_json(session, snapshot.generated_at)
                     for session in snapshot.sessions],
        "orphan_runs": [_hand_run_json(run, snapshot.generated_at)
                        for run in snapshot.orphan_runs],
        "totals": {
            "live_sessions": snapshot.live_sessions,
            "running_subagents": snapshot.running_subagents,
            "running_hand_runs": snapshot.running_hand_runs,
        },
    }
