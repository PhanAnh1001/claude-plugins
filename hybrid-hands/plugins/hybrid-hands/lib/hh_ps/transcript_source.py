"""Parse Claude transcript and subagent JSONL files without reading message text."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from .constants import (
    SILENT_AFTER_SECONDS, SUBAGENT_JSONL_SUFFIX, SUBAGENT_META_GLOB,
    SUBAGENT_META_SUFFIX, TRANSCRIPT_ASSISTANT_TYPE, TRANSCRIPT_TITLE_TYPE,
)
from .models import Subagent
from .timeutil import to_epoch


@dataclass
class TranscriptInfo:
    custom_title: str = ""
    cwd: str = ""
    context_tokens: Optional[int] = None
    started_at: Optional[float] = None
    last_activity: Optional[float] = None
    mtime: float = 0.0
    slug: str = ""


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _usage_context(message: Any) -> Optional[int]:
    usage = message.get("usage") if isinstance(message, dict) else None
    if not isinstance(usage, dict):
        return None
    total = 0
    for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        try:
            total += max(0, int(usage.get(key) or 0))
        except (TypeError, ValueError):
            continue
    return total


def _iter_objects(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    yield item
    except OSError:
        return


def parse_transcript(path: Path) -> TranscriptInfo:
    """Stream one transcript, keeping only title, cwd, usage and timestamps."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    info = TranscriptInfo(mtime=mtime, slug=path.parent.name)
    for item in _iter_objects(path):
        cwd = item.get("cwd")
        if isinstance(cwd, str) and cwd:
            info.cwd = cwd
        moment = to_epoch(item.get("timestamp"))
        if moment is not None:
            info.started_at = moment if info.started_at is None else min(
                info.started_at, moment)
            info.last_activity = moment if info.last_activity is None else max(
                info.last_activity, moment)
        if item.get("type") == TRANSCRIPT_TITLE_TYPE:
            title = item.get("customTitle")
            if isinstance(title, str) and title:
                info.custom_title = title
        elif item.get("type") == TRANSCRIPT_ASSISTANT_TYPE:
            context = _usage_context(item.get("message"))
            if context is not None:
                info.context_tokens = context
    info.last_activity = info.last_activity or info.mtime
    return info


def _parse_agent(path: Path) -> Tuple[Optional[int], Optional[float], Optional[float]]:
    context: Optional[int] = None
    first: Optional[float] = None
    last: Optional[float] = None
    if not path.is_file():
        return context, first, last
    for item in _iter_objects(path):
        moment = to_epoch(item.get("timestamp"))
        if moment is not None:
            first = moment if first is None else min(first, moment)
            last = moment if last is None else max(last, moment)
        if item.get("type") == TRANSCRIPT_ASSISTANT_TYPE:
            found = _usage_context(item.get("message"))
            if found is not None:
                context = found
    return context, first, last


def load_subagents(dirs: Iterable[Path], cutoff: float, now: float) -> List[Subagent]:
    agents: List[Subagent] = []
    for folder in dirs:
        for meta_path in sorted(folder.glob(SUBAGENT_META_GLOB)):
            meta = _read_json(meta_path) or {}
            agent_id = meta_path.name[len("agent-"):-len(SUBAGENT_META_SUFFIX)]
            jsonl = meta_path.with_name(
                meta_path.name[:-len(SUBAGENT_META_SUFFIX)] + SUBAGENT_JSONL_SUFFIX)
            context, first, last = _parse_agent(jsonl)
            try:
                mtime = (jsonl if jsonl.is_file() else meta_path).stat().st_mtime
            except OSError:
                mtime = meta_path.stat().st_mtime
            finished = meta.get("finished") is True
            if finished and mtime < cutoff:
                continue
            duration = None
            if first is not None:
                end = last if finished and last is not None else now
                duration = max(0.0, end - first)
            agents.append(Subagent(
                agent_id=agent_id,
                agent_type=str(meta.get("agentType") or ""),
                description=str(meta.get("description") or ""),
                finished=finished,
                silent=not finished and now - mtime > SILENT_AFTER_SECONDS,
                context_tokens=context,
                duration_seconds=duration,
                last_activity=mtime,
            ))
    agents.sort(key=lambda item: (item.finished, -(item.last_activity or 0.0)))
    return agents
