"""Parse Claude transcript and subagent JSONL files without reading message text."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .constants import (
    SILENT_AFTER_SECONDS, SUBAGENT_JSONL_SUFFIX, SUBAGENT_META_GLOB,
    SUBAGENT_META_SUFFIX, TRANSCRIPT_AI_TITLE_TYPE, TRANSCRIPT_ASSISTANT_TYPE,
    TRANSCRIPT_TITLE_TYPE,
)
from .models import Subagent, Usage
from .pricing import SYNTHETIC_MODEL, price_for, usage_usd
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
    ai_title: str = ""
    usage: Optional[Usage] = None
    model: str = ""
    effort: str = ""
    finished_at: Optional[float] = None


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


def _usage_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _cache_write_tokens(usage: dict) -> int:
    total = _usage_int(usage.get("cache_creation_input_tokens"))
    if total:
        return total
    detail = usage.get("cache_creation")
    if not isinstance(detail, dict):
        return 0
    return (_usage_int(detail.get("ephemeral_1h_input_tokens"))
            + _usage_int(detail.get("ephemeral_5m_input_tokens")))


def _usage_key(message: dict, item: dict) -> Optional[str]:
    message_id = message.get("id")
    request_id = item.get("requestId")
    if not message_id and not request_id:
        return None
    return f"{message_id or ''}|{request_id or ''}"


class _UsageAccumulator:
    """Sum assistant usage in one stream; the last record per message id wins."""

    def __init__(self, since: Optional[float] = None) -> None:
        self._by_key: Dict[str, Tuple[dict, str]] = {}
        self._extra: List[Tuple[dict, str]] = []
        self._since = since

    def add(self, item: dict) -> None:
        if self._since is not None:
            moment = to_epoch(item.get("timestamp"))
            if moment is not None and moment < self._since:
                return
        message = item.get("message")
        if not isinstance(message, dict):
            return
        usage = message.get("usage")
        if not isinstance(usage, dict):
            return
        model = str(message.get("model") or "")
        if model == SYNTHETIC_MODEL:
            return
        key = _usage_key(message, item)
        if key is None:
            self._extra.append((usage, model))
        else:
            self._by_key[key] = (usage, model)

    def result(self) -> Optional[Usage]:
        records = list(self._by_key.values()) + self._extra
        if not records:
            return None
        read = cache_read = cache_write = out = 0
        usd = 0.0
        priced = True
        for usage, model in records:
            read += _usage_int(usage.get("input_tokens"))
            cache_read += _usage_int(usage.get("cache_read_input_tokens"))
            cache_write += _cache_write_tokens(usage)
            out += _usage_int(usage.get("output_tokens"))
            price = price_for(model)
            if price is not None:
                usd += usage_usd(price, usage)
            else:
                priced = False
        return Usage(read=read, cache_read=cache_read, cache_write=cache_write,
                     out=out, usd=usd if priced else None, usd_estimated=True)


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


def parse_transcript(path: Path, since: Optional[float] = None) -> TranscriptInfo:
    """Stream one transcript, keeping only title, cwd, usage and timestamps."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    info = TranscriptInfo(mtime=mtime, slug=path.parent.name)
    usage = _UsageAccumulator(since)
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
        model, effort = _model_effort(item)
        info.model = model or info.model
        info.effort = effort or info.effort
        if _finished(item):
            info.finished_at = moment or info.finished_at
        kind = item.get("type")
        if kind == TRANSCRIPT_TITLE_TYPE:
            title = item.get("customTitle")
            if isinstance(title, str) and title:
                info.custom_title = title
        elif kind == TRANSCRIPT_AI_TITLE_TYPE:
            title = item.get("aiTitle")
            if isinstance(title, str):
                info.ai_title = title
        elif kind == TRANSCRIPT_ASSISTANT_TYPE:
            context = _usage_context(item.get("message"))
            if context is not None:
                info.context_tokens = context
            usage.add(item)
    info.usage = usage.result()
    info.last_activity = info.last_activity or info.mtime
    return info


def _parse_agent(
        path: Path, since: Optional[float] = None
) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[Usage]]:
    context: Optional[int] = None
    first: Optional[float] = None
    last: Optional[float] = None
    usage = _UsageAccumulator(since)
    if not path.is_file():
        return context, first, last, None
    for item in _iter_objects(path):
        moment = to_epoch(item.get("timestamp"))
        if moment is not None:
            first = moment if first is None else min(first, moment)
            last = moment if last is None else max(last, moment)
        if item.get("type") == TRANSCRIPT_ASSISTANT_TYPE:
            found = _usage_context(item.get("message"))
            if found is not None:
                context = found
            usage.add(item)
    return context, first, last, usage.result()


def _model_effort(item: dict) -> Tuple[str, str]:
    message = item.get("message")
    metadata = item.get("metadata")
    source = message if isinstance(message, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    return (str(item.get("model") or source.get("model") or metadata.get("model") or ""),
            str(item.get("effort") or item.get("reasoning_effort") or
                metadata.get("effort") or ""))


def _finished(item: dict) -> bool:
    return (item.get("finished") is True or
            item.get("type") in {"agent_finished", "session_end", "session-end"} or
            (item.get("type") == "result" and item.get("subtype") in
             {"success", "error", "error_max_turns", "error_during_execution"}))


def load_subagents(dirs: Iterable[Path], cutoff: float, now: float,
                   since: Optional[float] = None,
                   parent_ended: Optional[float] = None) -> List[Subagent]:
    agents: Dict[str, Subagent] = {}
    for folder in dirs:
        paths = {path.name[:-len(SUBAGENT_META_SUFFIX)] for path in
                 folder.glob(SUBAGENT_META_GLOB)}
        paths.update(path.stem for path in folder.glob("agent-*.jsonl"))
        for stem in sorted(paths):
            meta_path = folder / (stem + SUBAGENT_META_SUFFIX)
            jsonl = folder / (stem + SUBAGENT_JSONL_SUFFIX)
            meta = _read_json(meta_path) or {}
            context, first, last, usage = _parse_agent(jsonl, since)
            first = to_epoch(meta.get("started_at") or meta.get("startedAt")) or first
            finished = _finished(meta)
            model, effort = _model_effort(meta)
            agent_type = str(meta.get("agentType") or "")
            for item in _iter_objects(jsonl):
                found_model, found_effort = _model_effort(item)
                model, effort = found_model or model, found_effort or effort
                agent_type = str(item.get("agentType") or agent_type)
                finished = finished or _finished(item)
            finished = finished or parent_ended is not None
            try:
                mtime = (jsonl if jsonl.is_file() else meta_path).stat().st_mtime
            except OSError:
                continue
            activity = last or to_epoch(meta.get("ended_at") or meta.get("endedAt"))
            observed = activity or mtime
            if finished and observed < cutoff:
                continue
            end = activity if finished else now
            agent_id = stem[len("agent-"):]
            agents[agent_id] = Subagent(
                agent_id=agent_id, agent_type=agent_type,
                description=str(meta.get("description") or ""), finished=finished,
                silent=not finished and now - observed > SILENT_AFTER_SECONDS,
                context_tokens=context,
                duration_seconds=max(0.0, end - first) if first is not None and end is not None else None,
                last_activity=activity, usage=usage, started_at=first,
                model=model, effort=effort)
    return sorted(agents.values(), key=lambda item: (item.finished, -(item.last_activity or 0.0)))
