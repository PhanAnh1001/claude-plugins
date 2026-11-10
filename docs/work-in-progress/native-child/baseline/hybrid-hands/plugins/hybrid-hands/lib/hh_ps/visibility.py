"""Default `hh-ps` view: drop session trees whose every session has ended."""
from __future__ import annotations

from typing import Dict, List

from .models import Session, Snapshot


def _root_id(session: Session, by_id: Dict[str, Session]) -> str:
    current = session
    seen = {current.session_id}
    while current.parent_session and current.parent_session in by_id:
        parent = by_id[current.parent_session]
        if parent.session_id in seen:  # defensive: a cycle in side-session state
            break
        seen.add(parent.session_id)
        current = parent
    return current.session_id


def _tree_active(members: List[Session]) -> bool:
    return any(session.live
               or any(agent.running for agent in session.subagents)
               or any(run.running for run in session.hand_runs)
               for session in members)


def hide_ended_trees(snapshot: Snapshot) -> Snapshot:
    """Keep trees with a live session, running subagent or running hand run.

    Ended sessions inside a kept tree stay; orphan hand runs are untouched.
    """
    by_id = {session.session_id: session for session in snapshot.sessions}
    trees: Dict[str, List[Session]] = {}
    for session in snapshot.sessions:
        trees.setdefault(_root_id(session, by_id), []).append(session)
    keep = {session.session_id for members in trees.values()
            if _tree_active(members) for session in members}
    snapshot.hidden_ended_sessions = len(snapshot.sessions) - len(keep)
    snapshot.sessions = [s for s in snapshot.sessions if s.session_id in keep]
    return snapshot
