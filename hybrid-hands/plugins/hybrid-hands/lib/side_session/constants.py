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
}

PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"
PROVIDERS = (PROVIDER_CLAUDE, PROVIDER_CODEX)

SCREEN_PREFIX = "side-"
WATCH_SUFFIX = "-watch"
BRANCH_PREFIX = "side/"

STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
STATUS_CAPPED = "capped"
STATUS_DEAD = "dead"
ACTIVE_STATUSES = (STATUS_RUNNING,)

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
