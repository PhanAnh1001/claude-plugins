#!/bin/bash
# SessionStart: shared policy renderer, preserving the stable JSON envelope.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"
TEXT="$(python3 "$ROOT/lib/policy_mode.py" session "$ROOT")"
jq -n --arg ctx "$TEXT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
