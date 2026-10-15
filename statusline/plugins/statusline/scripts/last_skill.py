#!/usr/bin/env python3
"""Print the skill most recently loaded in a Claude Code session, for the status line.

Ported from dev-workflow plugin 0.3.0 (commit 65f7f95) plugins/dev-workflow/scripts/last_skill.py.
Differences: the max-bytes override env var is STATUSLINE_LAST_SKILL_MAX_BYTES.

Usage:
    last_skill.py <transcript_path>   # path given directly
    last_skill.py < statusline.json   # no argument: read the status-line JSON, use .transcript_path

Output: "\N{WRENCH} <skill name>" on one line with no trailing newline, or nothing at all.

Where the name comes from (newest record first, reading the JSONL transcript backwards):
  1. an assistant record whose message.content[] has {"type": "tool_use", "name": "Skill",
     "input": {"skill": "<name>"}} - works without any hook;
  2. fallback: an attachment {"type": "hook_system_message", "content": "\N{WRENCH} Skill: <name>"}
     written by a PreToolUse(Skill) hook such as the dev-workflow plugin's. Because that record is
     written after its tool_use, a hit first looks a few lines further back for the tool_use
     with the same toolUseID and prefers that tool_use's name.

Speed: the file is read backwards in blocks and the scan stops at the first hit; at most
MAX_READ_BYTES are read (override with env STATUSLINE_LAST_SKILL_MAX_BYTES, used by the tests).
Fail-open: missing file, bad JSON, cut-off lines or any OS error -> no output, exit 0.
Requires Python >= 3.9 (stdlib only), so the status line can use any PATH python3.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Iterator, Optional

EXIT_OK = 0
OUTPUT_PREFIX = "\N{WRENCH} "
# Upper bound on bytes read from the end of the transcript; a skill loaded earlier than this is
# not shown. 4 MB keeps the status line fast even for multi-MB transcripts.
MAX_READ_BYTES = 4 * 1024 * 1024
MAX_BYTES_ENV = "STATUSLINE_LAST_SKILL_MAX_BYTES"
READ_BLOCK_BYTES = 64 * 1024
# After a hook_system_message hit, how many older lines to search for the matching tool_use
# (in real transcripts it is 1-3 lines earlier).
TOOL_USE_LOOKBACK_LINES = 20
LINE_SEPARATOR = b"\n"
ENCODING = "utf-8"

TRANSCRIPT_PATH_KEY = "transcript_path"
MESSAGE_KEY = "message"
CONTENT_KEY = "content"
TYPE_KEY = "type"
NAME_KEY = "name"
ID_KEY = "id"
INPUT_KEY = "input"
ATTACHMENT_KEY = "attachment"
TOOL_USE_ID_KEY = "toolUseID"
TOOL_USE_TYPE = "tool_use"
SKILL_TOOL_NAME = "Skill"
HOOK_MESSAGE_TYPE = "hook_system_message"
HOOK_MESSAGE_PREFIX = "\N{WRENCH} Skill: "
# Field names that may hold the skill name in the Skill tool input.
SKILL_NAME_KEYS = ("skill", "name", "command")
# Cheap byte filters: a line without any of these cannot be a skill record, so it is not parsed.
LINE_MARKERS = (b'"' + SKILL_TOOL_NAME.encode(ENCODING) + b'"', HOOK_MESSAGE_TYPE.encode(ENCODING))


@dataclass(frozen=True)
class SkillHit:
    """One skill record found in the transcript."""

    name: Optional[str]
    tool_use_id: Optional[str]
    from_hook: bool


def iter_lines_backwards(path: str, max_bytes: int) -> Iterator[bytes]:
    """Yield complete lines of `path` from last to first, reading at most `max_bytes` bytes."""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        budget = max_bytes
        carry = b""
        while position > 0 and budget > 0:
            size = min(READ_BLOCK_BYTES, position, budget)
            position -= size
            budget -= size
            handle.seek(position)
            chunk = handle.read(size) + carry
            lines = chunk.split(LINE_SEPARATOR)
            carry = lines[0]
            for line in reversed(lines[1:]):
                yield line
        if position == 0:
            yield carry  # the first line of the file is complete; a partial head is dropped


def first_skill_name(tool_input: Any) -> Optional[str]:
    if not isinstance(tool_input, dict):
        return None
    for key in SKILL_NAME_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def tool_use_hits(record: dict) -> Iterator[SkillHit]:
    """Skill tool_use blocks of an assistant record, newest (last in content) first."""
    message = record.get(MESSAGE_KEY)
    content = message.get(CONTENT_KEY) if isinstance(message, dict) else None
    if not isinstance(content, list):
        return
    for block in reversed(content):
        if not isinstance(block, dict):
            continue
        if block.get(TYPE_KEY) == TOOL_USE_TYPE and block.get(NAME_KEY) == SKILL_TOOL_NAME:
            yield SkillHit(first_skill_name(block.get(INPUT_KEY)), block.get(ID_KEY), from_hook=False)


def hook_hit(record: dict) -> Optional[SkillHit]:
    attachment = record.get(ATTACHMENT_KEY)
    if not isinstance(attachment, dict) or attachment.get(TYPE_KEY) != HOOK_MESSAGE_TYPE:
        return None
    content = attachment.get(CONTENT_KEY)
    if not isinstance(content, str) or not content.startswith(HOOK_MESSAGE_PREFIX):
        return None
    name = content[len(HOOK_MESSAGE_PREFIX):].strip()
    return SkillHit(name or None, attachment.get(TOOL_USE_ID_KEY), from_hook=True)


def skill_hits(line: bytes) -> Iterator[SkillHit]:
    """Skill records in one transcript line; malformed or unrelated lines yield nothing."""
    if not any(marker in line for marker in LINE_MARKERS):
        return
    try:
        record = json.loads(line.decode(ENCODING))
    except (UnicodeDecodeError, ValueError):
        return
    if not isinstance(record, dict):
        return
    hit = hook_hit(record)
    if hit is not None:
        yield hit
        return
    yield from tool_use_hits(record)


def find_last_skill(path: str, max_bytes: int = MAX_READ_BYTES) -> Optional[str]:
    """Return the name of the most recently loaded skill in the transcript, or None."""
    fallback: Optional[SkillHit] = None
    lines_since_fallback = 0
    for line in iter_lines_backwards(path, max_bytes):
        if fallback is not None:
            lines_since_fallback += 1
            if lines_since_fallback > TOOL_USE_LOOKBACK_LINES:
                return fallback.name
        for hit in skill_hits(line):
            if fallback is None and hit.from_hook:
                if hit.name is not None:
                    fallback = hit
                continue
            if hit.from_hook or hit.name is None:
                continue
            if fallback is None or hit.tool_use_id == fallback.tool_use_id:
                return hit.name
    return fallback.name if fallback is not None else None


def read_max_bytes() -> int:
    raw = os.environ.get(MAX_BYTES_ENV, "")
    try:
        value = int(raw)
    except ValueError:
        return MAX_READ_BYTES
    return value if value > 0 else MAX_READ_BYTES


def transcript_path_from_stdin() -> Optional[str]:
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        return None
    path = payload.get(TRANSCRIPT_PATH_KEY) if isinstance(payload, dict) else None
    return path if isinstance(path, str) and path else None


def main(argv: list) -> int:
    path = argv[1] if len(argv) > 1 else transcript_path_from_stdin()
    if not path:
        return EXIT_OK
    try:
        name = find_last_skill(path, read_max_bytes())
    except OSError:
        return EXIT_OK
    if name:
        # Write bytes so a non-UTF-8 locale in the status-line environment cannot break the emoji.
        sys.stdout.buffer.write(f"{OUTPUT_PREFIX}{name}".encode(ENCODING))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
