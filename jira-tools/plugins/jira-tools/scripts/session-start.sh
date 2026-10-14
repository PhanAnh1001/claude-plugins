#!/bin/bash
# SessionStart hook: bơm đường dẫn CLI Jira và dự án khớp với cwd vào ngữ cảnh.
# Fail-open: mọi lỗi (thiếu python3, config hỏng, git treo) đều im lặng và thoát 0.
ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}"
OUTPUT="$(PYTHONPATH="$ROOT/lib" python3 -m jira_tools.session_context 2>/dev/null)" || exit 0
printf '%s\n' "$OUTPUT"
exit 0
