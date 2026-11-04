"""Named defaults and fixed strings for hand-ext (single source of truth)."""
from __future__ import annotations

from .backends.base import Status

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "ext_hand"
PLUGIN_PLACEHOLDER = "<PL>"  # replaced by the plugin directory in config paths

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
                "base_url": "https://opencode.ai/inference/go/openai/v1"},
        "opencode": {"config": "<PL>/templates/opencode-hand.jsonc",
                     "model": "opencode-go/deepseek-v4.1-flash", "variant": "max"},
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
