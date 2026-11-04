"""Named defaults and fixed strings for hand-ext (single source of truth)."""
from __future__ import annotations

from .backends.base import Status

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "ext_hand"
PLUGIN_PLACEHOLDER = "<PL>"  # replaced by the plugin directory in config paths

# Go usage ledger lives on the machine, not per repo: plan limits follow the account.
GO_USAGE_SECTION = "go_usage"
GO_USAGE_STATE_DIR_ENV = "HYBRID_HANDS_STATE_DIR"
GO_USAGE_DEFAULT_DIR = "~/.hybrid-hands"
GO_USAGE_LEDGER_NAME = "go_usage.jsonl"
GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD = 100.0
# Share of the monthly limit that each sliding window may use (OpenCode Go docs).
GO_USAGE_WINDOW_SHARES = (("5h", 5 * 3600, 0.2), ("7d", 7 * 86400, 0.5),
                          ("30d", 30 * 86400, 1.0))
# Backends billed through the OpenCode Go plan (DeepSeek V4.1 Flash).
GO_USAGE_BACKENDS = ("dsh", "opencode")
GO_PRICE_KEY = "go_price_per_mtok"
# Peak prices from https://opencode.ai/docs/go (read 2026-11-04), USD per 1M tokens:
# input $0.30, cached read $0.006, output $1.20. Off-peak is half; using peak keeps the
# estimate an upper bound, and the OpenCode Console remains the authoritative meter.
GO_USAGE_DEFAULT_PRICE = {"input": 0.30, "cached_input": 0.006, "output": 1.20}

DEFAULTS = {
    # Both default hands run DeepSeek V4.1 Flash on the OpenCode Go plan: dsh first, then
    # opencode. codex/claude/gemini stay declared for explicit `--backend` use only.
    "order": ["dsh", "opencode"],
    "timeout_min": 60,
    "max_tokens": None,
    "sandbox": "workspace-write",
    "ledger": "output/llm/hand_usage.json",
    "quota_state": "output/llm/hand_quota.json",
    "runs_dir": "output/llm/hand-ext",
    "backends": {
        "codex": {"home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "high"},
        "claude": {"config_dir": "~/.claude-hand", "model": "claude-opus-5-5",
                   "effort": "medium", "max_turns": 80},
        # DeepSeek Harness on the OpenCode Go key (templates/dsh-hand.yml); before opencode.
        "dsh": {"home": "~/.dsh-hand", "key_file": "~/.dsh-hand/go.key",
                "model": "deepseek-v4.1-flash", "effort": "max",
                "base_url": "https://opencode.ai/inference/go/openai/v1",
                "go_price_per_mtok": dict(GO_USAGE_DEFAULT_PRICE)},
        "opencode": {"config": "<PL>/templates/opencode-hand.jsonc",
                     "model": "opencode-go/deepseek-v4.1-flash", "variant": "max",
                     "go_price_per_mtok": dict(GO_USAGE_DEFAULT_PRICE)},
        "gemini": {"home": "~/.gemini-hand", "model": "gemini-4-carbon"},
    },
}

SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
AUTO_BACKEND = "auto"
ALL_BACKENDS = "all"
BROWSER_BACKEND = "dsh"  # only backend that can mount the Playwright MCP server

PREAMBLE_RELPATH = "templates/ext-hand-preamble.md"
BROWSER_RULES_RELPATH = "templates/ext-hand-browser-rules.md"
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
