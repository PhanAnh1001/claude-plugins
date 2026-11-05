"""hand-ext backend for the OpenCode CLI on the OpenCode Go subscription.

JSON event schema of `opencode run --format json` (one object per stdout line), read from
https://github.com/anomalyco/opencode at commit ffe6fed (dev, 2026-11-04):
- packages/cli/src/run/noninteractive.ts: every line is
  {"type", "timestamp", "sessionID", ...}; types `step_start`, `text` (part.text),
  `reasoning`, `tool_use`, `step_finish` (part.tokens, part.cost), `error` (error).
- packages/schema/src/token-usage.ts: tokens = {input, output, reasoning,
  cache: {read, write}}.
- packages/schema/src/session-error.ts: error = {type, message, status?, response?}.
- packages/core/src/session/to-session-error.ts: quota types `provider.go-limit`
  ("OpenCode Go ... usage limit reached"), `provider.quota`, `provider.free-limit`,
  `provider.budget-limit`, `provider.model-budget-limit`; login `provider.auth`.
Local CLI checked: opencode 1.19.5 (`opencode run --help`: --pure = no external plugins;
prompt only as positional message, so the brief is attached with -f). Its JSON keeps
`step_finish.part.cost` and tokens but not `opencode.allowance`; for Go usage within the plan
cost is 0, so the Go ledger estimates from tokens instead.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .base import Backend, Check, RunSpec, RunState, Status, bin_for
from ..constants import DEFAULT_COMPACT_AT

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PLUGIN_ROOT / "templates" / "opencode-hand.jsonc"
DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"
DEFAULT_VARIANT = "max"
REQUIRED_MODEL_PREFIX = "opencode-go/"  # subscription models only; others bill tokens
VARIANTS = frozenset({"low", "high", "max"})
AGENT_WRITE = "build"
AGENT_READONLY = "hand-readonly"  # defined in templates/opencode-hand.jsonc
SANDBOX_READONLY = "read-only"
PROMPT_FILE = "prompt.md"
SHORT_MESSAGE = ("Follow the attached brief (prompt.md) exactly. "
                 "End with the report format it asks for.")
CONFIG_ENV = "OPENCODE_CONFIG"
CONFIG_CONTENT_ENV = "OPENCODE_CONFIG_CONTENT"
COMPACTION_RESERVED = 20_000
COMPACTION_DISABLE_ENV = "OPENCODE_DISABLE_AUTOCOMPACT"
AUTH_PROVIDER_NAME = "OpenCode Go"
EXPECTED_RELEASE = "2026-10-17"  # DeepSeek V4.1 Flash 1017
# models.dev keeps release_date 2026-09-10 for opencode-go, but OpenCode announced on X
# (https://x.com/opencode/status/2112220734768779441, ~2026-10-20) that Go serves 1017 under
# the same id; so an older date is informational only and never fails doctor.
DOCTOR_TIMEOUT_S = 30
GO_DOCS_URL = "https://opencode.ai/docs/go/"

QUOTA_ERROR_TYPES = frozenset({
    "provider.go-limit", "provider.quota", "provider.free-limit",
    "provider.budget-limit", "provider.model-budget-limit"})
AUTH_ERROR_TYPES = frozenset({"provider.auth"})
QUOTA_PATTERN = re.compile(
    r"GoUsageLimitError|usage limit reached|QuotaExceeded|spend limit|"
    r"insufficient (credit|balance)|\b429\b", re.IGNORECASE)
AUTH_PATTERN = re.compile(
    r"\b401\b|unauthori[sz]ed|not logged in|no credentials|invalid api key|"
    r"opencode auth login", re.IGNORECASE)
RELEASE_PATTERN = re.compile(r'"release_date"\s*:\s*"([0-9-]+)"')

EV_TEXT = "text"
EV_STEP_FINISH = "step_finish"
EV_ERROR = "error"


def _opt(options: dict, key: str, default):
    value = options.get(key) if options else None
    return value if value else default


def _int_option(options: dict, key: str, default: int) -> int:
    value = (options or {}).get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} phải là số nguyên, nhận {value!r}")
    return value


def compact_at_option(options: dict) -> int:
    """Auto-compact threshold in tokens; 0 disables OPENCODE_CONFIG_CONTENT."""
    value = _int_option(options, "compact_at", DEFAULT_COMPACT_AT)
    if value < 0:
        raise ValueError(f"compact_at phải >= 0 (0 là tắt tự nén), nhận {value}")
    return value


def compaction_content(model: str, compact_at: int) -> str:
    """Inline config: limit.input - compaction.reserved == compact_at for this run."""
    provider, _, model_id = model.partition("/")
    if not provider or not model_id:
        raise ValueError(f"model phải có dạng provider/model, nhận {model!r}")
    if compact_at <= COMPACTION_RESERVED:
        raise ValueError(
            f"compact_at phải lớn hơn {COMPACTION_RESERVED} (reserved), nhận {compact_at}")
    return json.dumps({
        "compaction": {"auto": True, "reserved": COMPACTION_RESERVED},
        "provider": {provider: {"models": {model_id: {
            "limit": {"input": compact_at + COMPACTION_RESERVED}}}}},
    }, ensure_ascii=False, separators=(",", ":"))


class OpencodeBackend(Backend):
    name = "opencode"
    BLOCKED_ENV = ("OPENCODE_API_KEY", COMPACTION_DISABLE_ENV, "OPENAI_API_KEY",
                   "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                   "GOOGLE_GENERATIVE_AI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY")

    # ---- setup / doctor -------------------------------------------------
    def setup(self, options: dict) -> List[str]:
        return [
            "OpenCode Go hand: the user does these steps once (never automated):",
            "  1. opencode auth login   -> choose 'OpenCode Go' (subscription credential).",
            "  2. In OpenCode Console, Go page: turn OFF Extra Usage and keep Console credit"
            " at 0, so hitting the limit stops instead of billing tokens"
            " (" + GO_DOCS_URL + ").",
            "  3. Check with: hand-ext doctor --backend opencode",
            "Config used for runs: " + str(self._config(options)),
        ]

    def doctor(self, options: dict) -> List[Check]:
        model = _opt(options, "model", DEFAULT_MODEL)
        version = self._probe(["--version"])
        checks = [Check("installed", version is not None,
                        version.strip() if version else "opencode not found")]
        if version is None:
            return checks
        auth = self._probe(["auth", "list"]) or ""
        checks.append(Check("login", AUTH_PROVIDER_NAME in auth,
                            "credential '%s' %s" % (AUTH_PROVIDER_NAME,
                            "present" if AUTH_PROVIDER_NAME in auth else
                            "missing: run `opencode auth login`")))
        provider = model.split("/", 1)[0]
        models = self._probe(["models", provider]) or ""
        checks.append(Check("model", model in models.split(),
                            model + (" listed" if model in models.split() else " not listed")))
        checks.append(self._release_check(provider, model))
        config = self._config(options)
        checks.append(Check("config", config.is_file(), str(config)))
        return checks

    def _release_check(self, provider: str, model: str) -> Check:
        verbose = self._probe(["models", provider, "--verbose"]) or ""
        start = verbose.find(model)
        found = RELEASE_PATTERN.search(verbose, start if start >= 0 else 0)
        release = found.group(1) if found else "unknown"
        detail = "release_date %s" % release
        if release < EXPECTED_RELEASE:
            detail += (" (metadata cũ; OpenCode báo Go đã phục vụ bản 1017 dưới cùng id)")
        return Check("model_release", True, detail)

    def _probe(self, args: List[str]) -> Optional[str]:
        try:
            done = subprocess.run([bin_for(self.name)] + args, capture_output=True,
                                  text=True, timeout=DOCTOR_TIMEOUT_S, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout if done.returncode == 0 else None

    @staticmethod
    def _config(options: dict) -> Path:
        return Path(_opt(options, "config", str(DEFAULT_CONFIG))).expanduser()

    # ---- run ------------------------------------------------------------
    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        options = spec.options or {}
        model = spec.model or _opt(options, "model", DEFAULT_MODEL)
        if not model.startswith(REQUIRED_MODEL_PREFIX):
            raise ValueError("opencode backend only runs %s* subscription models, got %r"
                             % (REQUIRED_MODEL_PREFIX, model))
        variant = spec.effort if spec.effort in VARIANTS else _opt(
            options, "variant", DEFAULT_VARIANT)
        agent = AGENT_READONLY if spec.sandbox == SANDBOX_READONLY else AGENT_WRITE
        spec.run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = spec.run_dir / PROMPT_FILE
        prompt_path.write_text(spec.prompt, encoding="utf-8")
        argv = [bin_for(self.name), "run", "--pure", "--model", model,
                "--variant", variant, "--format", "json", "--dir", str(spec.cwd),
                "--agent", agent, "--auto", "-f", str(prompt_path), "--", SHORT_MESSAGE]
        env = {CONFIG_ENV: str(self._config(options))}
        compact_at = compact_at_option(options)
        if compact_at:
            env[CONFIG_CONTENT_ENV] = compaction_content(model, compact_at)
        return argv, env, None

    def parse_line(self, line: str, state: RunState) -> None:
        line = line.strip()
        if not line.startswith("{"):
            return
        try:
            event = json.loads(line)
        except ValueError:
            return
        kind = event.get("type")
        part = event.get("part") or {}
        if kind == EV_TEXT and part.get("text"):
            state.final_text = part["text"]
        elif kind == EV_STEP_FINISH:
            self._add_usage(part, state)
        elif kind == EV_ERROR:
            error = event.get("error") or {}
            state.errors.append("%s: %s" % (error.get("type", "unknown"),
                                            error.get("message", "")))
            state.extra.setdefault("error_types", []).append(error.get("type", ""))

    @staticmethod
    def _add_usage(part: dict, state: RunState) -> None:
        tokens = part.get("tokens") or {}
        cache = tokens.get("cache") or {}
        cached = int(cache.get("read", 0))
        state.usage.input += int(tokens.get("input", 0)) + cached + int(cache.get("write", 0))
        state.usage.cached_input += cached
        state.usage.output += int(tokens.get("output", 0)) + int(tokens.get("reasoning", 0))
        state.extra["cost_usd_reference"] = (state.extra.get("cost_usd_reference", 0.0)
                                             + float(part.get("cost") or 0))
        # The Console API reports the authoritative Go charge as opencode.allowance; some
        # future CLI may carry it on the event. The installed 1.19.5 does not, and part.cost
        # is 0 for Go within its limits, so this stays absent and cost falls back to tokens.
        meta = part.get("opencode") if isinstance(part.get("opencode"), dict) else {}
        allowance = part.get("allowance", meta.get("allowance",
                                                  part.get("opencode.allowance")))
        if isinstance(allowance, (int, float)) and not isinstance(allowance, bool):
            state.extra["go_allowance_usd"] = (state.extra.get("go_allowance_usd", 0.0)
                                               + float(allowance))

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        types = set(state.extra.get("error_types", []))
        text = "\n".join(state.errors) + "\n" + (stderr_text or "")
        if types & QUOTA_ERROR_TYPES or QUOTA_PATTERN.search(text):
            return Status.QUOTA
        if types & AUTH_ERROR_TYPES or AUTH_PATTERN.search(text):
            return Status.NOT_LOGGED_IN
        if exit_code != 0 or state.errors:
            return Status.FAILED
        return Status.OK
