"""Ngữ cảnh SessionStart: đường dẫn CLI và dự án Jira khớp với cwd của phiên.

Đọc JSON hook từ stdin (khoá ``cwd``), in JSON ``hookSpecificOutput`` ra stdout. Mọi lỗi được
``scripts/session-start.sh`` nuốt để hook không bao giờ chặn phiên.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Final

from jira_tools import config as jira_config
from jira_tools.errors import ConfigError

HOOK_EVENT_NAME: Final = "SessionStart"
CLI_RELATIVE_PATH: Final = "bin/jira-cli"


def _session_cwd(raw_stdin: str) -> str:
    try:
        payload: Any = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except ValueError:
        payload = {}
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    return str(cwd) if cwd else os.getcwd()


def _project_line(cwd: str) -> str:
    try:
        config = jira_config.load_config()
    except ConfigError as error:
        return f"Dự án Jira: không đọc được config ({error})."
    project = jira_config.match_project_by_repo(config, jira_config.current_repo_names(cwd))
    if project is None:
        return (
            "Dự án Jira: thư mục hiện tại không khớp dự án nào trong config/jira.json "
            "(lệnh create/meta cần --project hoặc JIRA_PROJECT)."
        )
    host = jira_config.resolve_base_url(jira_config.resolve_profile(config, project))
    return f"Dự án Jira khớp repo hiện tại: {project.key} (host {host})."


def build_context(cwd: str) -> str:
    cli = jira_config.PLUGIN_ROOT / CLI_RELATIVE_PATH
    return (
        f"Plugin jira-tools: gọi CLI Jira bằng đường dẫn tuyệt đối {cli} "
        f"(xem skill jira-tools:jira để biết lệnh).\n{_project_line(cwd)}"
    )


def main() -> int:
    cwd = _session_cwd(sys.stdin.read() if not sys.stdin.isatty() else "")
    output = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "additionalContext": build_context(cwd),
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
