#!/bin/bash
# Status-line helper: print the skills most recently loaded in a session, one line per agent, or nothing:
#   🔧 <skill of the main agent> (main)
#   🔧 <skill of a subagent> (<agent type>: "<description, cut to 30 chars + ...>")   (up to 3)
# --color paints the skill in Claude Code's inline-code colour (truecolor rgb 177,185,249) and dims
# the note in parentheses (DIM/RESET as in statusline.sh).
# Ported from dev-workflow plugin 0.3.0 (commit 65f7f95) plugins/dev-workflow/scripts/last-skill.sh.
# Difference: no fallback interpreter picker; without python3 on PATH it prints nothing.
# Usage: last-skill.sh [--color] <transcript_path>
#    or: <status-line JSON> | last-skill.sh [--color]   (no path: .transcript_path is read from stdin)
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
