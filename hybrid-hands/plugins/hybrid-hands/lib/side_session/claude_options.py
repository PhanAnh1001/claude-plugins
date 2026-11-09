"""Translate existing Claude process options to Paseo 0.15's SDK contract."""
from __future__ import annotations

import json

from . import commands as K
from .config import SideConfig

PERMISSION_FLAG = "--permission-mode"


def process_options(cfg: SideConfig, chrome: bool | None) -> dict:
    """Use supported modeId and providerOptions.extraArgs; do not add security policy."""
    argv = K.with_chrome(cfg.claude_args, K.chrome_enabled(cfg, chrome))
    mode = ""
    extra: dict[str, str | None] = {}
    index = 0
    while index < len(argv):
        flag = argv[index]
        if not flag.startswith("--"):
            raise ValueError("side-session: claude_args cần cờ --option cho Paseo")
        key, equals, value = flag[2:].partition("=")
        index += 1
        argument = value if equals else None
        if not equals and index < len(argv) and not argv[index].startswith("--"):
            argument = argv[index]
            index += 1
        if key == PERMISSION_FLAG[2:]:
            if not argument:
                raise ValueError("side-session: --permission-mode thiếu giá trị")
            mode = argument
        elif key not in ("model", "effort", "session-id", "resume"):
            extra[key] = argument
    if cfg.status_line_cmd:
        extra["settings"] = json.dumps({"statusLine": {
            "type": "command", "command": cfg.status_line_cmd}}, separators=(",", ":"))
    return {"mode_id": mode, "claude_options": {"extraArgs": extra}}
