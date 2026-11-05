"""Named defaults and fixed strings for `cc-switch` (single source of truth)."""
from __future__ import annotations

PASEO_HOME_ENV = "PASEO_HOME"
PASEO_HOME_DEFAULT = "~/.paseo"
AGENTS_SUBDIR = "agents"
AGENT_FILE_SUFFIX = ".json"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
EXIT_PASEO = 5

MIN_AGENT_PREFIX = 6
SHORT_ID_CHARS = 8
SHORT_ERROR_MAX_CHARS = 200
TITLE_MAX_CHARS = 40
PASEO_STATUS_WIDTH = 8
TUI_WIDTH = 10

HANDOFF_SUBDIR = "cc-switch"
HANDOFF_FILENAME = "handoff.json"
HANDOFF_TIME_FORMAT = "%H:%M"
UNKNOWN_TITLE = "(không tên)"
UNKNOWN_TIME = "-"
TRANSCRIPT_USER_TYPE = "user"

PASEO_TIMEOUT_SECONDS = 60
GIT_TIMEOUT_SECONDS = 5

PROVIDER_CLAUDE = "claude"
SESSION_ENTRYPOINT_TUI = "cli"
STATUS_RUNNING = "running"
PASEO_ACTIVE_STATUSES = ("running", "idle")

HOLDER_TERMINAL = "terminal"
HOLDER_PASEO = "paseo"
HOLDER_NONE = "không"

STATUS_HEADER = (
    f"{'ID8':<{SHORT_ID_CHARS}}  {'TITLE':<{TITLE_MAX_CHARS}}  "
    f"{'PASEO':<{PASEO_STATUS_WIDTH}}  {'SESSION':<{SHORT_ID_CHARS}}  "
    f"{'TUI':<{TUI_WIDTH}}  nơi đang giữ"
)
