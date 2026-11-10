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

# Store scopes (hh-store files.scope / claude_usage_lines.scope).
SCOPE_TRANSCRIPT = "claude_transcript"
SCOPE_SUBAGENT = "claude_subagent"


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


@dataclass(frozen=True)
class UsageRecord:
    """Usage-bearing fields of one assistant line; no message text."""
    at: Optional[float]
    key: Optional[str]
    usage: dict
    model: str


def usage_record(item: dict) -> Optional[UsageRecord]:
    message = item.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    return UsageRecord(at=to_epoch(item.get("timestamp")), key=_usage_key(message, item),
                       usage=usage, model=str(message.get("model") or ""))


@dataclass
class FileFold:
    """Metadata folded over every JSON object of one transcript/subagent file."""
    cwd: str = ""
    first: Optional[float] = None
    last: Optional[float] = None
    model: str = ""
    effort: str = ""
    finished: bool = False
    finished_at: Optional[float] = None
    custom_title: str = ""
    ai_title: str = ""
    context: Optional[int] = None
    agent_type: str = ""

    def add(self, item: dict) -> None:
        cwd = item.get("cwd")
        if isinstance(cwd, str) and cwd:
            self.cwd = cwd
        moment = to_epoch(item.get("timestamp"))
        if moment is not None:
            self.first = moment if self.first is None else min(self.first, moment)
            self.last = moment if self.last is None else max(self.last, moment)
        model, effort = _model_effort(item)
        self.model = model or self.model
        self.effort = effort or self.effort
        if item.get("agentType"):
            self.agent_type = str(item.get("agentType"))
        if _finished(item):
            self.finished = True
            self.finished_at = moment or self.finished_at
        kind = item.get("type")
        if kind == TRANSCRIPT_TITLE_TYPE:
            title = item.get("customTitle")
            if isinstance(title, str) and title:
                self.custom_title = title
        elif kind == TRANSCRIPT_AI_TITLE_TYPE:
            title = item.get("aiTitle")
            if isinstance(title, str):
                self.ai_title = title
        elif kind == TRANSCRIPT_ASSISTANT_TYPE:
            context = _usage_context(item.get("message"))
            if context is not None:
                self.context = context


@dataclass
class FileScan:
    fold: FileFold
    records: List[UsageRecord]


def parse_object(line: str) -> Optional[dict]:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        item = json.loads(line)
    except ValueError:
        return None
    return item if isinstance(item, dict) else None


def is_usage_line(item: dict) -> bool:
    return item.get("type") == TRANSCRIPT_ASSISTANT_TYPE


def _scan_legacy(path: Path) -> FileScan:
    scan = FileScan(FileFold(), [])
    for item in _iter_objects(path):
        scan.fold.add(item)
        if is_usage_line(item):
            record = usage_record(item)
            if record is not None:
                scan.records.append(record)
    return scan


def scan_file(path: Path, scope: str) -> FileScan:
    """Fold + usage records from the hh-store when available, else the whole file."""
    from hh_store.claude_ingest import scan_stored
    stored = scan_stored(path, scope)
    return stored if stored is not None else _scan_legacy(path)


class _UsageAccumulator:
    """Sum assistant usage in one stream; the last record per message id wins."""

    def __init__(self, since: Optional[float] = None) -> None:
        self._by_key: Dict[str, Tuple[dict, str]] = {}
        self._extra: List[Tuple[dict, str]] = []
        self._since = since

    def add(self, item: dict) -> None:
        record = usage_record(item)
        if record is not None:
            self.add_record(record)

    def add_record(self, record: "UsageRecord") -> None:
        if self._since is not None:
            if record.at is not None and record.at < self._since:
                return
        if record.model == SYNTHETIC_MODEL:
            return
        if record.key is None:
            self._extra.append((record.usage, record.model))
        else:
            self._by_key[record.key] = (record.usage, record.model)

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
                item = parse_object(line)
                if item is not None:
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
    scan = scan_file(path, SCOPE_TRANSCRIPT)
    fold = scan.fold
    info.cwd, info.started_at, info.last_activity = fold.cwd, fold.first, fold.last
    info.model, info.effort = fold.model, fold.effort
    info.finished_at = fold.finished_at
    info.custom_title, info.ai_title = fold.custom_title, fold.ai_title
    info.context_tokens = fold.context
    info.usage = _usage_from(scan.records, since)
    info.last_activity = info.last_activity or info.mtime
    return info


def _usage_from(records: Iterable[UsageRecord], since: Optional[float]) -> Optional[Usage]:
    usage = _UsageAccumulator(since)
    for record in records:
        usage.add_record(record)
    return usage.result()


def _parse_agent(path: Path, since: Optional[float] = None
                 ) -> Tuple[Optional[FileFold], Optional[Usage]]:
    if not path.is_file():
        return None, None
    scan = scan_file(path, SCOPE_SUBAGENT)
    return scan.fold, _usage_from(scan.records, since)


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
            fold, usage = _parse_agent(jsonl, since)
            fold = fold or FileFold()
            context, first, last = fold.context, fold.first, fold.last
            first = to_epoch(meta.get("started_at") or meta.get("startedAt")) or first
            model, effort = _model_effort(meta)
            model, effort = fold.model or model, fold.effort or effort
            agent_type = fold.agent_type or str(meta.get("agentType") or "")
            finished = _finished(meta) or fold.finished
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
