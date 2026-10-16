#!/bin/bash
# SessionStart hook: when the repo has .claude/dev-workflow.toml, remind the agent to use the
# dev-workflow skills and how to run the helper scripts. Without the config it prints nothing.
# Fail-open: never blocks the session, never touches the network, always exits 0.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CONFIG_FILE="$PROJECT_DIR/.claude/dev-workflow.toml"
[ -f "$CONFIG_FILE" ] || exit 0

case "${BASH_SOURCE[0]}" in
  */*) HOOK_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) HOOK_DIR="." ;;
esac
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOOK_DIR/..}"
SCRIPTS_DIR="$PLUGIN_ROOT/scripts"
DW="$SCRIPTS_DIR/dw"

# shellcheck source=_pick_python.sh
. "$SCRIPTS_DIR/_pick_python.sh" 2>/dev/null || exit 0

echo "This repository uses the dev-workflow plugin (config: .claude/dev-workflow.toml)."
echo "- Start any task that changes code or docs with the skill dev-workflow:dev-triage. Requests that only touch Jira, close the session or check traceability go straight to dev-workflow:jira-workflow, dev-workflow:session-closeout or dev-workflow:trace-check."
echo "- Finish the session with the skill dev-workflow:session-closeout (gate, plan ticks, traceability, Jira)."
echo "- Merged config: \"$DW\" config [--get section.key] [--json]"
echo "- Traceability: \"$DW\" trace [--write] [--format md|json]"
echo "- Template to use (repo override or plugin): \"$DW\" template <design|plan|bug|cr|adr|traceability>"
if ! dw_pick_python; then
  echo "- Warning: no Python >= 3.11 or uv found on PATH; \"$DW\" will fail until one is installed."
fi
exit 0
