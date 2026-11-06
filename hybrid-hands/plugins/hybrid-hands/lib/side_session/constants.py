"""Named constants for side-session (single source of truth).

Ported from live-tiktok-games docs/work-in-progress/2026-11-03-live-room-game-orchestration.md §7.
"""
from __future__ import annotations

CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "side_session"

# Section 7.3 of the source plan: execution cap = max(300k, 150k x estimated hours).
DEFAULT_MAX_TOKENS = 300_000
TOKENS_PER_HOUR = 150_000
# Source plan: watchdog warns above 80 % of the cap.
WARN_RATIO = 0.8
# Soft cap: false keeps counting and warning but never stops the session at the cap.
DEFAULT_ENFORCE_TOKEN_CAP = True
# `ls` TOKENS/CAP suffix when tokens_used >= max_tokens (both cap modes).
OVER_CAP_SUFFIX = " !"
# One `watch` warning per tick when the cap is exceeded with enforce_token_cap=false.
OVER_CAP_WARNING = "{name}: over cap {used}/{cap} (không dừng: enforce_token_cap=false)"
# Source plan: final summary block is at most 15 lines.
SUMMARY_MAX_LINES = 15
SUMMARY_HEADING = "## Tóm tắt"

DEFAULTS: dict = {
    "handoff_dir": "docs/work-in-progress/handoffs",
    "worktree_root": "../{repo}-wt",
    "max_parallel": 2,
    "default_max_tokens": DEFAULT_MAX_TOKENS,
    "watch_interval_s": 30,
    "claude_args": ["--permission-mode", "bypassPermissions", "--no-chrome"],
    "state_dir": "output/llm/side-sessions",
    "codex_home": "~/.codex-hand",
    "codex_profile": "",  # empty: use top-level keys of the hand-only CODEX_HOME
    # argv of the day-budget guard, e.g. ["scripts/day-budget.sh", "status"]; [] = off.
    "budget_check_cmd": [],
    # status line command for claude side sessions (relative to repo), "" = Claude default.
    "status_line_cmd": "",
    # status-line token file for claude side sessions (relative to repo), "" = transcript.
    "token_file": "",
    # true = stop at the token cap; false = keep running and only warn.
    "enforce_token_cap": DEFAULT_ENFORCE_TOKEN_CAP,
}

PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"
PROVIDER_DSH = "dsh"
PROVIDERS = (PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_DSH)
# Providers run as an external hand through `hand-ext run` (no Claude transcript).
EXTERNAL_PROVIDERS = (PROVIDER_DSH,)

SCREEN_PREFIX = "side-"
WATCH_SUFFIX = "-watch"
BRANCH_PREFIX = "side/"
DEFAULT_BASE = "HEAD"

STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
STATUS_CAPPED = "capped"
STATUS_DEAD = "dead"
STATUS_DAYSTOP = "daystop"
ACTIVE_STATUSES = (STATUS_RUNNING,)

# Exit codes of `side-session start`/`watch`.
EXIT_USAGE = 2
EXIT_BUDGET = 4

# Day-budget guard: `budget_check_cmd` exits 20 when today's budget is spent.
BUDGET_DAYSTOP_CODE = 20
BUDGET_TIMEOUT_S = 30

PARENT_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
CHILD_SESSION_ENV = "CLAUDE_CODE_CHILD_SESSION"

CHROME_FLAG = "--chrome"
NO_CHROME_FLAG = "--no-chrome"
PROMPT_RULES_MARKER = "LUẬT BẮT BUỘC"

# External-hand contract: label side:<name>, prompt file and report in the hand-ext run dir.
EXT_LABEL_PREFIX = "side:"
# hand-ext sanitises ':' to '-', so the registry may hold this form instead.
EXT_LABEL_SANITIZED_PREFIX = "side-"
PROMPT_FILE_SUFFIX = ".prompt.md"
EXT_REPORT_FILE = "report.md"
HAND_RUN_STATUS_OK = "ok"

CLAUDE_PROJECTS_DIR = "~/.claude/projects"
# Env override for the projects dir (tests point it at a fixture tree).
CLAUDE_PROJECTS_ENV = "SIDE_SESSION_CLAUDE_PROJECTS"
CODEX_SESSIONS_SUBDIR = "sessions"
CODEX_ROLLOUT_GLOB = "rollout-*.jsonl"

TEMPLATE_RELPATH = "templates/side-session-prompt.md"
BRAIN_PLACEHOLDER = "{brain}"
NAME_PLACEHOLDER = "{name}"
HANDOFF_PLACEHOLDER = "{handoff}"
BRAIN_LINE_MARKER = "[[brain]]"

TOKEN_FILE_PLACEHOLDER = "{uuid}"
RESUME_PROMPT = ("Phiên này được mở lại sau khi bị dừng. Đọc lại việc đang dở, "
                 "không làm lại bước đã xong, rồi làm tiếp đến hết theo yêu cầu ban đầu.")
