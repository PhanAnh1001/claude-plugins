"""Named defaults and fixed strings for hand-ext (single source of truth)."""
from __future__ import annotations

from .backends.base import Status
from usage_pricing import token_price

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "ext_hand"
PLUGIN_PLACEHOLDER = "<PL>"  # replaced by the plugin directory in config paths

# Legacy names remain aliases for the numbered Claude account registry.
# v1 stops once this machine has used max_day_pct of the weekly limit today; `day_guard: false`
# turns that off, `day_guard_off_date: "YYYY-MM-DD"` turns it off for that local day only.
# The plugin default is `day_guard: false`; `day_guard_days` limits it to listed weekdays.
CLAUDE_MAIN_BACKEND = "claude-main"
CLAUDE_MAIN_CONFIG_DIR = "~/.claude"
CLAUDE_MAIN_MODEL = "claude-opus-5-5"
CLAUDE_MAIN_EFFORT = "low"
CLAUDE_MAIN_MAX_TURNS = 80
CLAUDE_MAIN_MAX_DAY_PCT = 8.0

# Machine state dir (run registry, Codex ledger, ladder log, worktrees): per machine,
# not per repo. The env override is used by tests and isolated setups.
STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
STATE_DIR_DEFAULT = "~/.hybrid-hands"

# Codex usage ledger (one JSON line per finished codex turn) in the machine state dir.
CODEX_PRICE_KEY = "price_per_mtok"
# gpt-6.1-sol Standard, context <=272k, from https://developers.openai.com/api/docs/pricing
# (read 2026-11-07): USD per 1M tokens. Codex compacts at 272k, so the short tier applies.
CODEX_DEFAULT_PRICE = {("cached" if key == "cached_input" else key): value
                       for key, value in (token_price("gpt-6.1-sol") or {}).items()}
CODEX_USAGE_LEDGER_NAME = "codex_usage.jsonl"
# Live registry of run attempts (one JSON per run under <state>/runs, machine-wide).
HAND_RUNS_SUBDIR = "runs"
HAND_RUNS_UPDATE_SECONDS = 15.0
HAND_RUNS_RETENTION_SECONDS = 7 * 86400
HAND_RUN_STATUS_RUNNING = "running"
# Auto worktree GC before each isolated run: "finished" removes only clean, owned,
# finished worktrees; "off" disables it. Preserved/dirty/unknown are never auto-removed.
WORKTREE_GC_FINISHED = "finished"
WORKTREE_GC_OFF = "off"
WORKTREE_GC_MODES = (WORKTREE_GC_FINISHED, WORKTREE_GC_OFF)
# Auto GC scans every worktree (git status each); at most once per hour machine-wide.
WORKTREE_GC_AUTO_INTERVAL_SECONDS = 3600
WORKTREE_GC_AUTO_STAMP = "worktree-gc-auto.stamp"
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
    "account_sync": {"sources": {"claude": "v1"}, "items": [],
                     "exclude": [], "settings": {"shared_keys": ["statusLine", "hooks"]}},
    "mode": "shell",
    "paseo": {},
    "native": {"claude": "auto", "codex": "auto"},
    "max_parallel": MAX_PARALLEL,
    "claude_accounts": {
        "v1": {"config_dir": "~/.claude", "max_day_pct": CLAUDE_MAIN_MAX_DAY_PCT,
               # Off by default (16/11/2026); enable per repo/global, optionally limited
               # to local weekdays with `day_guard_days: ["sat", "sun"]`.
               "day_guard": False},
        "v2": {"config_dir": "~/.claude-hand"},
    },
    # Label-only registry (optional plan/name per slot); codex still runs from backends.codex.
    "gpt_accounts": {"v1": {"home": "~/.codex"}},
    "account_label_format": "{provider} {slot} {plan} {name}",
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
    "worktree_gc": {"auto": WORKTREE_GC_FINISHED},
    "backends": {
        "codex": {"home": "~/.codex", "model": "gpt-6.1-sol", "effort": "low",
                  CODEX_PRICE_KEY: dict(CODEX_DEFAULT_PRICE)},
        "claude": {"config_dir": "~/.claude-hand", "model": "claude-opus-5-5",
                   "effort": "low", "max_turns": 80},
        # Compatibility alias for the v1 account.
        "claude-main": {"config_dir": CLAUDE_MAIN_CONFIG_DIR, "model": CLAUDE_MAIN_MODEL,
                        "effort": CLAUDE_MAIN_EFFORT, "max_turns": CLAUDE_MAIN_MAX_TURNS,
                        "max_day_pct": CLAUDE_MAIN_MAX_DAY_PCT},
    },
}

# Backends removed from the plugin; legacy `ext_hand.backends.<name>` entries are dropped silently.
RETIRED_BACKENDS = frozenset({"dsh", "gemini"})

SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
# `--backend auto` is no longer accepted by run/pick: a role or an explicit backend is.
AUTO_BACKEND = "auto"
ALL_BACKENDS = "all"

PREAMBLE_RELPATH = "templates/ext-hand-preamble.md"
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
# The selected account/backend cannot run (quota, not logged in, day guard). The name is
# kept from the removed order fallback so callers and docs keep the same number.
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

# Provider capabilities are deliberately independent of the pricing registry.
MODEL_CAPABILITIES = {
    "claude": frozenset({"claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5",
                         "claude-haiku-5-5"}),
    "codex": frozenset({"gpt-6.1-sol", "gpt-6.1-terra"}),
}
PROVIDER_EFFORTS = {
    "claude": ("low", "medium", "high", "max"),
    "codex": ("low", "medium", "high", "xhigh"),
}
# Repo profile → role table (see hand_ext.profiles); config keys `profile` and `profiles`.
PROFILE_KEY = "profile"
PROFILE_OVERRIDES_KEY = "profiles"
PROFILE_NAMES = ("claude-mono", "gpt-mono", "hybrid")
EFFORT_ALIASES = {"codex": {"max": "xhigh"}}
