#!/bin/bash
# PreToolUse hook (matcher: Skill): show the user "🔧 Skill: <name>" each time a skill is loaded.
# Always on (does not read .claude/dev-workflow.toml). Only ever prints a systemMessage; never
# blocks or changes the tool call. Fail-open: any error -> no output, exit 0.
# skill_notice.py only needs `json` (Python >= 3.9), so the plain PATH python3 is used first;
# dw_pick_python (tomllib probe, maybe uv) is only a fallback because it is slower and uv may
# download Python on first use, which could exceed the hook timeout.

FAST_PYTHON="python3"

case "${BASH_SOURCE[0]}" in
  */*) SCRIPTS_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) SCRIPTS_DIR="." ;;
esac

if command -v "$FAST_PYTHON" >/dev/null 2>&1; then
  PYTHON_CMD=("$FAST_PYTHON")
else
  # shellcheck source=_pick_python.sh
  . "$SCRIPTS_DIR/_pick_python.sh" 2>/dev/null || exit 0
  dw_pick_python || exit 0
  PYTHON_CMD=("${DW_PYTHON[@]}")
fi

"${PYTHON_CMD[@]}" "$SCRIPTS_DIR/skill_notice.py" 2>/dev/null
exit 0
