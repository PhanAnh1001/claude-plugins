"""Named defaults and fixed strings for hand-ext (single source of truth)."""
from __future__ import annotations

from .backends.base import Status
from usage_pricing import token_price

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "ext_hand"
PLUGIN_PLACEHOLDER = "<PL>"  # replaced by the plugin directory in config paths
# Auto-compaction threshold for each hand run (tokens); 0 disables it per backend.
DEFAULT_COMPACT_AT = 272_000
# dsh model window from templates/dsh-hand.yml; compaction is a ratio of this window.
DEFAULT_CONTEXT_WINDOW = 1_048_576

# Legacy names remain aliases for the numbered Claude account registry.
# v1 stops once this machine has used max_day_pct of the weekly limit today.
CLAUDE_MAIN_BACKEND = "claude-main"
CLAUDE_MAIN_CONFIG_DIR = "~/.claude"
CLAUDE_MAIN_MODEL = "claude-opus-5-5"
CLAUDE_MAIN_EFFORT = "low"
CLAUDE_MAIN_MAX_TURNS = 80
CLAUDE_MAIN_MAX_DAY_PCT = 5.0

# Go usage ledger lives on the machine, not per repo: plan limits follow the account.
GO_USAGE_SECTION = "go_usage"
GO_USAGE_STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
GO_USAGE_DEFAULT_DIR = "~/.hybrid-hands"
GO_USAGE_LEDGER_NAME = "go_usage.jsonl"
GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD = 100.0
GO_USAGE_LIVE_KEY = "live"
GO_USAGE_LIVE_DEFAULT = True
# Live Go numbers come from the statusline plugin's fetch script and its shared cache.
GO_LIVE_ENV = "HYBRID_HANDS_GO_LIVE"
GO_FETCH_ENV = "HYBRID_HANDS_GO_FETCH"
GO_SUMMARY_PREFIX = "hạn mức: "
GO_ESTIMATE_PREFIX = "ước tính từ sổ: "
GO_LIVE_MISSING = ("hạn mức Go (thật): chưa lấy được "
                   "(cần plugin statusline và đăng nhập OpenCode Go)")
# Share of the monthly limit that each sliding window may use (OpenCode Go docs).
GO_USAGE_WINDOW_SHARES = (("5h", 5 * 3600, 0.2), ("7d", 7 * 86400, 0.5),
                          ("30d", 30 * 86400, 1.0))
# Backends billed through the OpenCode Go plan (DeepSeek V4.1 Flash). "opencode" was a
# backend until 0.19.0; it stays here so its old ledger lines still count toward the plan.
GO_USAGE_BACKENDS = ("dsh", "opencode")
GO_PRICE_KEY = "go_price_per_mtok"
# Peak prices from https://opencode.ai/docs/go (read 2026-11-04), USD per 1M tokens:
# input $0.30, cached read $0.006, output $1.20. Off-peak is half; using peak keeps the
# estimate an upper bound, and the OpenCode Console remains the authoritative meter.
GO_USAGE_DEFAULT_PRICE = token_price("deepseek-v4.1-flash") or {}

# Codex usage ledger (one JSON line per finished codex turn), beside the Go ledger.
CODEX_PRICE_KEY = "price_per_mtok"
# gpt-6.1-sol Standard, context <=272k, from https://developers.openai.com/api/docs/pricing
# (read 2026-11-07): USD per 1M tokens. Codex compacts at 272k, so the short tier applies.
CODEX_DEFAULT_PRICE = {("cached" if key == "cached_input" else key): value
                       for key, value in (token_price("gpt-6.1-sol") or {}).items()}
CODEX_USAGE_LEDGER_NAME = "codex_usage.jsonl"
# Capacity (429 prefill_cap_refused) fallback for `--backend auto` on dsh.
DSH_CAPACITY_WAIT_MIN_LINES = 30
DSH_CAPACITY_WAIT_SECONDS = 180
DSH_CAPACITY_MAX_CONTINUATIONS = 2
CODEX_FALLBACK_MODEL = "gpt-6.1-sol"
CODEX_FALLBACK_EFFORT = "low"

# Live registry of run attempts (one JSON per run under <state>/runs, machine-wide).
HAND_RUNS_SUBDIR = "runs"
HAND_RUNS_UPDATE_SECONDS = 15.0
HAND_RUNS_RETENTION_SECONDS = 7 * 86400
HAND_RUN_STATUS_RUNNING = "running"
PARENT_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
PARENT_CLAUDE_PID_ENV = "CLAUDE_PID"
RUN_REGISTRY_WARNING = "cảnh báo: không ghi được sổ lượt hand"

# Isolation of a run from the caller's working tree (see lib/hand_ext/isolation.py).
ISOLATION_WORKTREE = "worktree"
ISOLATION_NONE = "none"
ISOLATIONS = (ISOLATION_WORKTREE, ISOLATION_NONE)
WORKTREES_DIRNAME = "worktrees"
CHANGES_PATCH_FILE = "changes.patch"
APPLY_OK = "ok"
APPLY_CONFLICT = "conflict"
APPLY_EMPTY = "empty"
APPLY_SKIPPED = "skipped"
APPLY_ERROR = "error"
# Second isolation layer: untracked files whose basename looks like a secret never enter
# the hand's worktree, even when the repo forgot to ignore them. Basename match, fnmatch.
SECRET_FILE_PATTERNS = (
    ".env", ".env.*", "*.env", "*.pem", "*.key", "id_rsa*", ".netrc", ".npmrc", ".pypirc",
)
SECRET_FILE_ALLOW = (".env.example", ".env.sample", ".env.template", "*.env.example")
SECRET_SKIP_PREFIX = "- Bỏ qua file nghi bí mật: "
SYMLINK_OUTSIDE_NOTE = "symlink tuyệt đối hoặc ra ngoài repo hoặc tới file bí mật"

MAX_PARALLEL = 4
HAND_SCOPE_ENV = "HYBRID_HANDS_HAND_SCOPE"

DEFAULTS = {
    "mode": "shell",
    "paseo": {},
    "native": {"claude": "auto", "codex": "auto"},
    "max_parallel": MAX_PARALLEL,
    "order": ["dsh", "codex", "claude-v1", "claude-v2"],
    "claude_accounts": {
        "v1": {"config_dir": "~/.claude", "max_day_pct": 5.0},
        "v2": {"config_dir": "~/.claude-hand"},
    },
    "timeout_min": 60,
    "max_tokens": None,
    "sandbox": "workspace-write",
    "ledger": "output/llm/hand_usage.json",
    "quota_state": "output/llm/hand_quota.json",
    "runs_dir": "output/llm/hand-ext",
    # Default when cwd is a git repo; a non-git cwd falls back to none with a warning.
    # worktree_root is outside the repo; without an explicit value it follows
    # HYBRID_HANDS_STATE_DIR (default ~/.hybrid-hands/worktrees).
    "isolation": ISOLATION_WORKTREE,
    "worktree_root": "~/.hybrid-hands/worktrees",
    "backends": {
        "codex": {"home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "low",
                  CODEX_PRICE_KEY: dict(CODEX_DEFAULT_PRICE)},
        "claude": {"config_dir": "~/.claude-hand", "model": "claude-opus-5-5",
                   "effort": "low", "max_turns": 80},
        # Compatibility alias for the v1 account.
        "claude-main": {"config_dir": CLAUDE_MAIN_CONFIG_DIR, "model": CLAUDE_MAIN_MODEL,
                        "effort": CLAUDE_MAIN_EFFORT, "max_turns": CLAUDE_MAIN_MAX_TURNS,
                        "max_day_pct": CLAUDE_MAIN_MAX_DAY_PCT},
        # DeepSeek Harness on the OpenCode Go key (templates/dsh-hand.yml).
        "dsh": {"home": "~/.dsh-hand", "key_file": "~/.dsh-hand/go.key",
                "model": "deepseek-v4.1-flash", "effort": "off",
                "base_url": "https://opencode.ai/inference/go/openai/v1",
                "compact_at": DEFAULT_COMPACT_AT,
                "context_window": DEFAULT_CONTEXT_WINDOW,
                "go_price_per_mtok": dict(GO_USAGE_DEFAULT_PRICE),
                "capacity_wait_min_lines": DSH_CAPACITY_WAIT_MIN_LINES,
                "capacity_wait_seconds": DSH_CAPACITY_WAIT_SECONDS},
        "gemini": {"home": "~/.gemini-hand", "model": "gemini-4-carbon"},
    },
}

SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
AUTO_BACKEND = "auto"
ALL_BACKENDS = "all"
BROWSER_BACKEND = "dsh"  # only backend that can mount the Playwright MCP server

PREAMBLE_RELPATH = "templates/ext-hand-preamble.md"
BROWSER_RULES_RELPATH = "templates/ext-hand-browser-rules.md"
TEST_REMINDER_RELPATH = "templates/ext-hand-test-reminder.md"
BRIEF_HEADER = "\n\n## BRIEF\n\n"
REPORT_FILE = "report.md"
EVENTS_FILE = "events.jsonl"
STDERR_FILE = "stderr.log"
REPORT_PREVIEW_LINES = 60

POLL_SECONDS = 1.0  # how often backend.poll() and the caps are checked
TERM_GRACE_SECONDS = 5.0  # wait after SIGTERM before SIGKILL
SECONDS_PER_MINUTE = 60
LABEL_MAX_LEN = 40
# Quota reset unknown: assume the 5-hour rolling window of subscription plans.
DEFAULT_QUOTA_BACKOFF_HOURS = 5

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_CAPPED = 4
EXIT_TIMEOUT = 6
EXIT_ALL_UNAVAILABLE = 7
EXIT_PARALLEL_FULL = 8

STATUS_EXIT = {
    Status.OK: EXIT_OK,
    Status.FAILED: EXIT_FAIL,
    Status.CAPPED: EXIT_CAPPED,
    Status.TIMEOUT: EXIT_TIMEOUT,
    Status.QUOTA: EXIT_ALL_UNAVAILABLE,
    Status.NOT_LOGGED_IN: EXIT_ALL_UNAVAILABLE,
}
# Statuses after which `--backend auto` tries the next backend in order.
FALLBACK_STATUSES = (Status.QUOTA, Status.NOT_LOGGED_IN)
