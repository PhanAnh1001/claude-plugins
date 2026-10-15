#!/bin/bash
# Status-line helper: print "🔧 <skill>" (plus " (<agent type>)" when a subagent loaded it) for the skill
# most recently loaded in a session by the main agent or a recent subagent, or nothing.
# Ported from dev-workflow plugin 0.3.0 (commit 65f7f95) plugins/dev-workflow/scripts/last-skill.sh.
# Difference: no fallback interpreter picker; without python3 on PATH it prints nothing.
# Usage: last-skill.sh <transcript_path>
#    or: <status-line JSON> | last-skill.sh        (no argument: .transcript_path is read from stdin)
# Reads the transcript backwards with a byte cap (see last_skill.py). Fail-open: any error ->
# no output, exit 0. last_skill.py only needs the stdlib of Python >= 3.9.

PYTHON="python3"

case "${BASH_SOURCE[0]}" in
  */*) SCRIPTS_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) SCRIPTS_DIR="." ;;
esac

command -v "$PYTHON" >/dev/null 2>&1 || exit 0

"$PYTHON" "$SCRIPTS_DIR/last_skill.py" "$@" 2>/dev/null
exit 0
