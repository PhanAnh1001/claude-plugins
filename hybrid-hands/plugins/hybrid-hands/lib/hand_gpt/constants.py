"""Named defaults and fixed strings for hand-gpt (single source of truth)."""
from __future__ import annotations

import enum

PROJECT_CONFIG_RELPATH = ".claude/hybrid-hands.json"
CONFIG_SECTION = "gpt_hand"

# Prices per 1M tokens, GPT-6.1 Sol Flex (https://developers.openai.com/api/docs/pricing, 11/2026).
DEFAULT_PRICES = {
    "input": 1.0,
    "cached_input": 0.05,
    "output": 5.0,
    "long_threshold": 272000,  # prompt tokens above which long-context prices apply
    "long_input": 2.0,
    "long_cached_input": 0.1,
    "long_output": 7.5,
}
PRICING_SOURCE_URL = "https://developers.openai.com/api/docs/pricing"
TOKENS_PER_PRICE_UNIT = 1_000_000

DEFAULTS = {
    "codex_home": "~/.codex-hand",
    "model": "gpt-6.1-sol",
    "service_tier": "flex",
    "effort": "medium",
    "sandbox": "workspace-write",
    "max_usd": 1.0,
    "approval_usd": 1.5,
    "timeout_min": 60,
    "ledger": "output/llm/codex_usage.json",
    "runs_dir": "output/llm/hand-gpt",
    "prices": DEFAULT_PRICES,
}

EFFORTS = ("low", "medium", "high", "xhigh", "max")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
STANDARD_TIER = "default"

# service_tier="flex" is honoured by codex only from this version (openai/codex#37813).
MIN_CODEX_VERSION = (0, 156, 0)
CODEX_BIN_ENV = "HAND_GPT_CODEX_BIN"
CODEX_DEFAULT_BIN = "codex"
LOGIN_COMMAND = "CODEX_HOME={home} codex login --with-api-key"
AUTH_FILE = "auth.json"
CONFIG_FILE = "config.toml"
# Legacy table written by early hand-gpt setup; codex >= 0.166 treats -p as profile v2 files.
LEGACY_PROFILE_HEADER = "[profiles.hand]"
SESSIONS_DIR = "sessions"

# Rough brief-size estimate: ~4 characters per token for mixed Vietnamese/English text.
CHARS_PER_TOKEN = 4
PREAMBLE_RELPATH = "templates/gpt-hand-preamble.md"
REPORT_FILE = "report.md"
EVENTS_FILE = "events.jsonl"
STDERR_FILE = "stderr.log"
REPORT_PREVIEW_LINES = 60

POLL_SECONDS = 1.0  # how often the runner re-reads the rollout while codex runs
TERM_GRACE_SECONDS = 5.0  # wait after SIGTERM before SIGKILL
LABEL_MAX_LEN = 40

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_NEEDS_APPROVAL = 3
EXIT_CAPPED = 4
EXIT_FLEX_REJECTED = 5
EXIT_TIMEOUT = 6

# Substrings (lower-case) in codex error messages that mean the Flex tier refused the request.
FLEX_REJECT_MARKERS = (
    "429",
    "resource_unavailable",
    "resource unavailable",
    "flex",
    "service_tier",
    "service tier",
    "capacity",
    "high demand",
    "overloaded",
)


class Status(str, enum.Enum):
    OK = "ok"
    FAILED = "failed"
    CAPPED = "capped"
    TIMEOUT = "timeout"
    FLEX_REJECTED = "flex_rejected"
    NEEDS_APPROVAL = "needs_approval"


STATUS_EXIT = {
    Status.OK: EXIT_OK,
    Status.FAILED: EXIT_FAIL,
    Status.CAPPED: EXIT_CAPPED,
    Status.TIMEOUT: EXIT_TIMEOUT,
    Status.FLEX_REJECTED: EXIT_FLEX_REJECTED,
    Status.NEEDS_APPROVAL: EXIT_NEEDS_APPROVAL,
}
