"""Named defaults and fixed strings for `hh-ps` (single source of truth)."""
from __future__ import annotations

SCHEMA_VERSION = 1
DEFAULT_SINCE_SECONDS = 6 * 3600
SINCE_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
MIN_WATCH_SECONDS = 2
ENDED_FLAG = "--ended"

CLAUDE_CONFIG_ENV = "CLAUDE_CONFIG_DIR"
CLAUDE_CONFIG_DEFAULT = "~/.claude"
SESSIONS_SUBDIR = "sessions"
PROJECTS_SUBDIR = "projects"
SUBAGENTS_SUBDIR = "subagents"
TRANSCRIPT_SUFFIX = ".jsonl"
SESSION_FILE_GLOB = "*.json"
SUBAGENT_META_GLOB = "agent-*.meta.json"
SUBAGENT_META_SUFFIX = ".meta.json"
SUBAGENT_JSONL_SUFFIX = ".jsonl"
SILENT_AFTER_SECONDS = 30 * 60

PARENT_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
PARENT_CLAUDE_PID_ENV = "CLAUDE_PID"

STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
STATE_DIR_DEFAULT = "~/.hybrid-hands"
RUNS_SUBDIR = "runs"
RUNS_GLOB = "*.json"
RUN_STATUS_RUNNING = "running"
PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"
SIDE_RUN_LABEL_PREFIX = "side:"
# hand-ext sanitises ":" to "-", so the registry holds side-<name>.
SIDE_RUN_LABEL_SANITIZED_PREFIX = "side-"
# Compact side-session name in the text tree and the pane: `phụ:<name>`.
SIDE_NAME_PREFIX = "phụ:"
SIDE_UNKNOWN_HEADING = "phiên phụ chưa rõ phiên cha"

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
PS_SECTION = "ps"
SESSION_META_GLOBS_KEY = "session_meta_globs"
SESSION_META_SUFFIX = ".meta"
SIDE_SESSION_SECTION = "side_session"
SIDE_STATE_DIR_KEY = "state_dir"
SIDE_STATE_DIR_DEFAULT = "output/llm/side-sessions"
REPO_PLACEHOLDER = "{repo}"

TRANSCRIPT_TITLE_TYPE = "custom-title"
TRANSCRIPT_AI_TITLE_TYPE = "ai-title"
TRANSCRIPT_ASSISTANT_TYPE = "assistant"

STATUS_BUSY = "busy"
STATUS_IDLE = "idle"
STATUS_ENDED = "đã kết thúc"
LIVE_STATUSES = (STATUS_BUSY, STATUS_IDLE)
SUBAGENT_RUNNING = "đang chạy"
SUBAGENT_FINISHED = "xong"
SUBAGENT_SILENT = "im lặng"
RUN_STATE_RUNNING = "running"
RUN_STATE_FINISHED = "finished"
RUN_STATE_LOST = "lost"
# Short on purpose: the README explains it (a `running` run whose pid is dead).
RUN_LOST_TEXT = "mất"
ORPHAN_HEADING = "hand ngoài không rõ phiên gọi"

# Row marks shared with hh-tree-pane (hooks/tree.ts keeps the same glyphs).
HERE_MARK = "▶"
LIVE_DOT = "●"
ENDED_DOT = "○"
CHILD_RUNNING_MARK = "▶"
CHILD_OK_MARK = "✓"
CHILD_BAD_MARK = "✗"
LEGEND = ("▶ phiên này ● sống ○ đã dừng · kết thúc = giờ local · "
          "USD ước tính · % tài khoản 5h/tuần · riêng = phần của lượt")
# Two-cell tree art keeps nested rows narrow enough for a pane beside the chat.
BRANCH = "├ "
LAST_BRANCH = "└ "
PIPE = "│ "
SPACE = "  "
COLOR_RESET = "\033[0m"
COLORS = {
    "busy": "\033[32m",
    "idle": "\033[33m",
    "ended": "\033[2m",
    "running": "\033[32m",
    "lost": "\033[31m",
    "finished": "\033[2m",
    "main": "\033[1;36m",
}
NO_COLOR_ENV = "NO_COLOR"
# Display-cell caps that keep child rows within 100 cells and session rows
# within 92 after the USD/% cells, so the tree still fits a narrow pane
# beside the chat. Session, side and child rows share one lead column (session
# name + tree art), so the description cap stays short.
DESCRIPTION_MAX_LEN = 16
SESSION_NAME_MAX_LEN = 16
KIND_MAX_LEN = 8
KIND_ALIASES = {"hybrid-hands:hand": "hand", "opencode": "oc"}
# Child statuses that print no text: the ✓ mark already says it.
OK_STATUSES = frozenset({"ok", "finished", "xong"})
STATUS_ALIASES = {"quota_exhausted": "quota"}
ELLIPSIS = "…"
# Finished or failed children listed under each session (newest end first);
# the rest fold into one `+N xong · M lỗi` line. hh-tree-pane (hooks/tree.ts)
# keeps the same number. `--full` lists every child.
RECENT_FINISHED_SHOWN = 3
FULL_FLAG = "--full"
SUMMARY_OK_TEXT = "xong"
SUMMARY_BAD_TEXT = "lỗi"
