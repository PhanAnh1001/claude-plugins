"""Locate subagent transcripts of a Claude Code session and label them, for last_skill.py.

Layout written by Claude Code (checked on CLI 2.1.29x):
  <project dir>/<session_id>.jsonl                               main transcript (transcript_path)
  <project dir>/<session_id>/subagents/agent-<agentId>.jsonl     one transcript per subagent
  <project dir>/<session_id>/subagents/agent-<agentId>.meta.json {"agentType": "plugin:name", ...}
A subagent's Skill tool_use and the PreToolUse hook message for it are written only to its own
transcript, never to the main one, so the status line has to read these files too.

Every helper is fail-open: a missing directory, unreadable or malformed meta -> empty / default.
Requires Python >= 3.9 (stdlib only).
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

TRANSCRIPT_SUFFIX = ".jsonl"
SUBAGENTS_DIRNAME = "subagents"
AGENT_TRANSCRIPT_GLOB = "agent-*" + TRANSCRIPT_SUFFIX
META_SUFFIX = ".meta.json"
AGENT_TYPE_KEY = "agentType"
# agentType is "<plugin>:<agent>" for plugin agents (e.g. "parallel-subagents:hand"); only the
# part after the last separator is shown to keep the status line short.
AGENT_TYPE_SEPARATOR = ":"
DEFAULT_AGENT_LABEL = "subagent"
ENCODING = "utf-8"
# Record timestamps look like "2026-10-14T09:31:10.793Z"; Python 3.9 fromisoformat rejects "Z".
UTC_SUFFIX = "Z"
UTC_OFFSET = "+00:00"


@dataclass(frozen=True)
class SubagentTranscript:
    """One subagent transcript file and its last-modified time (epoch seconds)."""

    path: str
    mtime: float


def subagents_dir(transcript_path: str) -> str:
    """<dirname>/<session_id>/subagents for a main transcript <dirname>/<session_id>.jsonl."""
    directory, filename = os.path.split(transcript_path)
    session_id = filename[: -len(TRANSCRIPT_SUFFIX)] if filename.endswith(TRANSCRIPT_SUFFIX) else filename
    return os.path.join(directory, session_id, SUBAGENTS_DIRNAME)


def _mtime_or_none(path: str) -> Optional[float]:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def recent_subagent_transcripts(directory: str, limit: int) -> List[SubagentTranscript]:
    """The `limit` most recently modified agent-*.jsonl files in `directory`, newest first."""
    if limit <= 0 or not os.path.isdir(directory):
        return []
    found = []
    for path in glob.glob(os.path.join(glob.escape(directory), AGENT_TRANSCRIPT_GLOB)):
        mtime = _mtime_or_none(path)
        if mtime is not None:
            found.append(SubagentTranscript(path, mtime))
    found.sort(key=lambda item: item.mtime, reverse=True)
    return found[:limit]


def _read_meta(transcript_path: str) -> Any:
    meta_path = transcript_path[: -len(TRANSCRIPT_SUFFIX)] + META_SUFFIX
    try:
        with open(meta_path, encoding=ENCODING) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def agent_label(transcript_path: str) -> str:
    """Short agent type from the meta file next to the transcript, or DEFAULT_AGENT_LABEL."""
    meta = _read_meta(transcript_path)
    agent_type = meta.get(AGENT_TYPE_KEY) if isinstance(meta, dict) else None
    if not isinstance(agent_type, str):
        return DEFAULT_AGENT_LABEL
    label = agent_type.rsplit(AGENT_TYPE_SEPARATOR, 1)[-1].strip()
    return label or DEFAULT_AGENT_LABEL


def parse_timestamp(value: Any) -> Optional[float]:
    """Epoch seconds of an ISO-8601 record timestamp, or None when missing or malformed."""
    if not isinstance(value, str) or not value:
        return None
    text = value[: -len(UTC_SUFFIX)] + UTC_OFFSET if value.endswith(UTC_SUFFIX) else value
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()
