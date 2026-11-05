"""Read Paseo agent records, keeping only the fields cc-switch may expose."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .constants import MIN_AGENT_PREFIX, PROVIDER_CLAUDE, TITLE_MAX_CHARS
from .errors import CcSwitchError
from .models import Agent
from .paths import agent_files, display, read_json, same_path, short_id


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _nested(raw: dict, key: str, field: str) -> str:
    value = raw.get(key)
    if not isinstance(value, dict):
        return ""
    return _text(value.get(field))


def agent_from_record(raw: dict, fallback_id: str) -> Agent:
    return Agent(
        id=_text(raw.get("id")) or fallback_id,
        cwd=_text(raw.get("cwd")),
        provider=_text(raw.get("provider")),
        title=_text(raw.get("title")),
        last_activity=_text(raw.get("lastActivityAt")),
        last_status=_text(raw.get("lastStatus")),
        runtime_session=_nested(raw, "runtimeInfo", "sessionId"),
        runtime_model=_nested(raw, "runtimeInfo", "model"),
        persistence_session=_nested(raw, "persistence", "sessionId"),
        archived=bool(raw.get("archivedAt")),
    )


def load_agents() -> List[Agent]:
    found: Dict[str, Agent] = {}
    for path in agent_files():
        raw = read_json(path)
        if raw is None:
            continue
        agent = agent_from_record(raw, path.stem)
        if not agent.id:
            continue
        previous = found.get(agent.id)
        if previous is None or agent.last_activity > previous.last_activity:
            found[agent.id] = agent
    return sorted(found.values(), key=lambda item: (item.title.lower(), item.id))


def project_agents(agents: List[Agent], root: Path) -> List[Agent]:
    return [agent for agent in agents
            if agent.provider == PROVIDER_CLAUDE and not agent.archived
            and same_path(agent.cwd, root)]


def match_agent_ref(agents: List[Agent], reference: str) -> List[Agent]:
    exact = [agent for agent in agents if agent.id == reference]
    if exact:
        return exact
    if len(reference) < MIN_AGENT_PREFIX:
        raise CcSwitchError(
            f"Tiền tố agent phải có ít nhất {MIN_AGENT_PREFIX} ký tự.")
    return [agent for agent in agents if agent.id.startswith(reference)]


def by_session(agents: List[Agent], session_id: str) -> List[Agent]:
    return [agent for agent in agents
            if session_id in (agent.runtime_session, agent.persistence_session)]


def preferred_agent(matches: List[Agent]) -> Agent:
    return sorted(matches, key=lambda agent: agent.archived)[0]


def describe_agent(agent: Agent, index: Optional[int] = None) -> str:
    prefix = f"  {index}. " if index is not None else "  "
    title = display(agent.title or "(không tên)", TITLE_MAX_CHARS)
    return (f"{prefix}{short_id(agent.id)}  {title}  "
            f"{agent.last_activity or '-'}  {agent.last_status or '-'}")
