#!/usr/bin/env python3
"""PreToolUse hook body for the Skill tool: tell the user which skill was loaded.

Reads the hook payload (JSON) from stdin and prints {"systemMessage": "<prefix><skill name>"}.
It never blocks or changes the tool call: no permissionDecision, decision or continue keys.
Fail-open: on any problem (empty stdin, bad JSON, no skill name) it prints nothing and exits 0.
Requires Python >= 3.9 (stdlib `json` only; no tomllib), so the hook can use any PATH python3.
"""
from __future__ import annotations

import json
import sys
from typing import Any

EXIT_OK = 0
TOOL_INPUT_KEY = "tool_input"
# Field names that may hold the skill name in the Skill tool input; "skill" is the observed one,
# the others are fallbacks in case the tool schema changes.
SKILL_NAME_KEYS = ("skill", "name", "command")
SYSTEM_MESSAGE_KEY = "systemMessage"
NOTICE_PREFIX = "\N{WRENCH} Skill: "


def extract_skill_name(payload: Any) -> str | None:
    """Return the skill name from a hook payload, or None when it cannot be found."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get(TOOL_INPUT_KEY)
    if not isinstance(tool_input, dict):
        return None
    for key in SKILL_NAME_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_notice(skill_name: str) -> str:
    """Return the hook output JSON for one skill name."""
    return json.dumps({SYSTEM_MESSAGE_KEY: f"{NOTICE_PREFIX}{skill_name}"}, ensure_ascii=False)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        return EXIT_OK
    skill_name = extract_skill_name(payload)
    if skill_name is not None:
        print(build_notice(skill_name))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
