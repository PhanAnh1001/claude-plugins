"""Locate subagent transcripts of a Claude Code session and label them, for last_skill.py.

Layout written by Claude Code (checked on CLI 2.1.29x):
  <project dir>/<session_id>.jsonl                               main transcript (transcript_path)
  <project dir>/<session_id>/subagents/agent-<agentId>.jsonl     one transcript per subagent
  <project dir>/<session_id>/subagents/agent-<agentId>.meta.json {"agentType": "plugin:name",
                                                                   "description": "...", ...}
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
DESCRIPTION_KEY = "description"
# agentType is "<plugin>:<agent>" for plugin agents (e.g. "parallel-subagents:hand"); only the
# part after the last separator is shown to keep the status line short.
AGENT_TYPE_SEPARATOR = ":"
DEFAULT_AGENT_LABEL = "subagent"
# Longer descriptions are cut to this many characters (enough to tell parallel subagents apart
# while one status-line row stays short) and DESCRIPTION_CUT_MARK is appended.
SUBAGENT_DESCRIPTION_MAX_CHARS = 30
# Plain ASCII dots, not "\N{HORIZONTAL ELLIPSIS}", so the width is the same in every terminal.
DESCRIPTION_CUT_MARK = "..."
# The description is printed inside double quotes, so a double quote in it becomes a single one.
DESCRIPTION_QUOTE = '"'
DESCRIPTION_QUOTE_REPLACEMENT = "'"
# Label layouts: '<agent>: "<description start>"', or '<agent>' without a description.
LABEL_WITH_DESCRIPTION = '{agent}: "{description}"'
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


def clean_text(text: str) -> str:
    """One line of text: non-printable characters become spaces, whitespace runs collapse."""
    printable = "".join(char if char.isprintable() else " " for char in text)
    return " ".join(printable.split())


def short_description(text: str) -> str:
    """Cleaned text with quotes made single; when longer than SUBAGENT_DESCRIPTION_MAX_CHARS
    characters (not bytes), its first that many characters, trailing spaces dropped, plus
    DESCRIPTION_CUT_MARK."""
    cleaned = clean_text(text).replace(DESCRIPTION_QUOTE, DESCRIPTION_QUOTE_REPLACEMENT)
    if len(cleaned) <= SUBAGENT_DESCRIPTION_MAX_CHARS:
        return cleaned
    return cleaned[:SUBAGENT_DESCRIPTION_MAX_CHARS].rstrip() + DESCRIPTION_CUT_MARK


def short_agent_type(meta: dict) -> str:
    """"hand" for "parallel-subagents:hand"; DEFAULT_AGENT_LABEL when missing or blank."""
    agent_type = meta.get(AGENT_TYPE_KEY)
    if not isinstance(agent_type, str):
        return DEFAULT_AGENT_LABEL
    return clean_text(agent_type.rsplit(AGENT_TYPE_SEPARATOR, 1)[-1]) or DEFAULT_AGENT_LABEL


def subagent_label(transcript_path: str) -> str:
    """Label from the meta file next to the transcript: 'hand: "<description start>"', 'hand'
    when there is no description, DEFAULT_AGENT_LABEL when the meta is missing or broken."""
    meta = _read_meta(transcript_path)
    if not isinstance(meta, dict):
        return DEFAULT_AGENT_LABEL
    agent = short_agent_type(meta)
    description = meta.get(DESCRIPTION_KEY)
    start = short_description(description) if isinstance(description, str) else ""
    return LABEL_WITH_DESCRIPTION.format(agent=agent, description=start) if start else agent


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
