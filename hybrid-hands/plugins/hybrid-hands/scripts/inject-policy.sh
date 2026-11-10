#!/bin/bash
# UserPromptSubmit: the same repository mode as SessionStart.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"
python3 "$ROOT/lib/policy_mode.py" prompt "$ROOT"
