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

# Codex provider defaults for the Sol side session.
# Context threshold for native Codex compaction; not a cumulative spending cap.
CODEX_AUTO_COMPACT_TOKEN_LIMIT = 272_000
HAND_SCOPE_ENV = "HYBRID_HANDS_HAND_SCOPE"
CODEX_MODEL_DEFAULT = "gpt-6.1-sol"
CODEX_EFFORT_DEFAULT = "high"
# Sol runs unconfined with no approval prompts (user decision 07/11): the screen path uses
# the CLI flag, the Paseo path the equivalent config pair (provider options, no CLI flag).
CODEX_FULL_ACCESS_FLAG = "--dangerously-bypass-approvals-and-sandbox"
CODEX_APPROVAL = "never"
CODEX_SANDBOX = "danger-full-access"

DEFAULTS: dict = {
    "handoff_dir": "docs/work-in-progress/handoffs",
    "worktree_root": "../{repo}-wt",
    "max_parallel": 4,
    "default_max_tokens": DEFAULT_MAX_TOKENS,
    "watch_interval_s": 30,
    "claude_args": ["--permission-mode", "bypassPermissions", "--no-chrome"],
    "state_dir": "output/llm/side-sessions",
    "codex_home": "~/.codex-hand",
    "codex_profile": "",  # empty: use top-level keys of the hand-only CODEX_HOME
    # Sol's Codex model/effort; `start --model/--effort` overrides them.
    "codex_model": CODEX_MODEL_DEFAULT,
    "codex_effort": CODEX_EFFORT_DEFAULT,
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
STATUS_IDLE = "idle"
STATUS_IDLE_NO_DONE = "idle_no_done"
# Create sent a request but the outcome is unknown: keep the slot and block the name.
STATUS_UNKNOWN = "unknown"
STATUS_ERROR = "error"
STATUS_STOPPED = "stopped"
STATUS_CAPPED = "capped"
STATUS_DEAD = "dead"
STATUS_DAYSTOP = "daystop"
STATUS_DONE = "done"
ACTIVE_STATUSES = (STATUS_RUNNING, STATUS_IDLE, STATUS_IDLE_NO_DONE, STATUS_UNKNOWN)

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

# Paseo transport (installed CLI 0.15.0; internal client/daemon-target modules).
TRANSPORT_SCREEN = "screen"
TRANSPORT_PASEO = "paseo"
PASEO_BIN = "paseo"
PASEO_NODE = "node"
PASEO_BRIDGE_RELPATH = "paseo_bridge.mjs"
PASEO_CONNECT_TIMEOUT_MS = 3000
PASEO_READY_TIMEOUT_S = 10
PASEO_START_TIMEOUT_S = 30
PASEO_STATUS_TIMEOUT_S = 15
PASEO_STOP_TIMEOUT_S = 15
# Never let a side session resolve an ambient Paseo agent/workspace.
PASEO_INHERITED_ENVS = ("PASEO_AGENT_ID", "PASEO_WORKSPACE_ID")
# Explicit test/offline escape hatch; normal runs never set it.
PASEO_DISABLE_ENV = "SIDE_SESSION_NO_PASEO"
PASEO_PROVIDER = "codex-hand"
PASEO_AGENT_RUNNING = "running"
PASEO_AGENT_INITIALIZING = "initializing"
PASEO_AGENT_IDLE = "idle"
PASEO_AGENT_ERROR = "error"
PASEO_AGENT_CLOSED = "closed"
PASEO_AGENT_ALIVE = (PASEO_AGENT_RUNNING, PASEO_AGENT_INITIALIZING)
PASEO_AGENT_DEAD = (PASEO_AGENT_ERROR, PASEO_AGENT_CLOSED)
PASEO_AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
PASEO_TARGET_CHANGED = "TARGET_CHANGED"
PASEO_PROFILE_UNSUPPORTED = "CODEX_PROFILE_UNSUPPORTED"
# Only failures known to occur before agent creation may release the slot.
# AGENT_CREATE_FAILED also covers lost replies after mutation, so stays unknown.
PASEO_CREATE_REJECTED = frozenset({"WORKSPACE_CREATE_FAILED",
                                   "TARGET_CHANGED", "PASEO_CLI_NOT_FOUND", "NODE_NOT_FOUND"})
# Codex native compaction is a top-level config.toml key in the hand-only CODEX_HOME.
CODEX_COMPACT_KEY = "model_auto_compact_token_limit"
# Native `codex app-server` config writer: stdio JSON-RPC, no thread/turn/model listing.
CODEX_APP_SERVER = "codex"
CODEX_CONFIG_CLIENT_NAME = "side_session_config"
CODEX_CONFIG_CLIENT_VERSION = "1"
CODEX_CONFIG_RPC_TIMEOUT_S = 15
CODEX_CONFIG_RPC_EXIT_S = 5
CODEX_CONFIG_RPC_KILL_S = 2

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
CODEX_TEMPLATE_RELPATH = "templates/side-session-prompt-codex.md"
BRAIN_PLACEHOLDER = "{brain}"
NAME_PLACEHOLDER = "{name}"
HANDOFF_PLACEHOLDER = "{handoff}"
DONE_PLACEHOLDER = "{done}"
HAND_EXT_PLACEHOLDER = "{hand_ext}"
BRAIN_LINE_MARKER = "[[brain]]"

# A session writes <handoff>.md then creates <handoff>.done as its finish contract.
DONE_SUFFIX = ".done"

TOKEN_FILE_PLACEHOLDER = "{uuid}"
RESUME_PROMPT = ("Phiên này được mở lại sau khi bị dừng. Đọc lại việc đang dở, "
                 "không làm lại bước đã xong, rồi làm tiếp đến hết theo yêu cầu ban đầu.")
