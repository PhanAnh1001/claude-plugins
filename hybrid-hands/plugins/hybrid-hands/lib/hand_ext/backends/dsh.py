"""hand-ext backend for DeepSeek Harness (`dsh --profile headless`) on the OpenCode Go plan.

Facts read from the installed @deepseek-ai/dsh 0.2.1-rc.5 (npm tag latest, 2026-11-04):
- dsh/lib/bin.js runCli(): every `--profile` run calls `loadLayeredEnv("dsh")` first.
- dsh-app-boot/lib/index.js loadLayeredEnv()/readEnvLayer(): reads `<process cwd>/.env` and
  `$DSH_HOME/.env` with readFileSync whatever the environment holds, and copies every name
  not already set into process.env. Setting the key in the env does NOT stop the read.
  So the wrapper launches dsh from an empty dir (`<home>/launch`) and points the workspace at
  the repo through the patch (`fs-sandbox.cwd`, `bash-sandbox.cwd`, `sandbox-policy`).
- dsh-headless/lib/json-stream-*.js: `--json` NDJSON events `session`, `status`
  (phase turn_start|step_start|step_end{usage}|turn_end{reason}), `text`, `thinking`,
  `tool_call`, `tool_result`, `final` {text}; runner failures emit `error` {message}.
  usage = {inputTokens, outputTokens, totalTokens?, cacheReadTokens?, cacheWriteTokens?,
  reasoningTokens?}; turn_end reason = {kind: completed|aborted|error, error?: {code, message}}.
- No spend data leaves dsh: dsh-llm-pi-ai/lib/index.js:271-280 says the harness never reads
  pi-ai's cost metadata and no consumer reports spend, and dsh-headless json-stream
  lines 214-226 publish only the token usage fields above (no cost/allowance).
- dsh-llm-pi-ai classifyPiAiError(): 401/403 -> AUTH, quota text -> QUOTA, 429 -> RATE_LIMIT;
  missing key -> MISSING_CREDENTIAL. The patch (templates/dsh-hand.yml) routes model calls
  through pi-ai `openai-completions` to the Go endpoint with `x-opencode-session` header.

Browser (`--browser`) facts read from the same install:
- dsh-app-boot/lib/index.js applyEntryPatches() (lines 61-109) applies `{insert: [entry]}`
  by appending entries; `name` is the plugin module specifier (schema description lines
  3013 and 3043-3044). A patch list is therefore `[{insert: [{id, name, config}]}]`.
- dsh/lib/bin.js lines 27-28, 60 and 105: `--patch` is repeatable and applied in argv order
  (profile-boot-C14i-8IN.js lines 231-245), so the browser MCP entry can live in a per-run
  overlay while the shared `hand.patch.yml` stays untouched.
- dsh-mcp-client/lib/index.js lines 781-801: stdio config schema (`transport`, `serverName`,
  `command`, `args`, `env`, `cwd`); lines 38-48 build the StdioClientTransport; lines 26-30
  pass `{...scrubbedParentEnv(), ...config.env}` as the child environment.
- dsh-subprocess/lib/index.js line 32: scrubbedParentEnv() drops names matching
  /KEY|PASSWORD|SECRET|TOKEN/i and every `DSH_*` name, so OPENCODE_GO_API_KEY does not reach
  the MCP server unless explicitly re-added. This backend adds only PLAYWRIGHT_BROWSERS_PATH.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .base import (Backend, CAPACITY_NOTE, Check, RunSpec, RunState, Status, bin_for,
                   is_capacity_error)
from ..constants import DEFAULT_COMPACT_AT, DEFAULT_CONTEXT_WINDOW

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATCH = PLUGIN_ROOT / "templates" / "dsh-hand.yml"
PATCH_FILE = "hand.patch.yml"  # copy of the template inside DSH_HOME, used by runs
LAUNCH_DIR = "launch"  # dir without `.env` dsh is started from, so it never reads the repo's
ENV_FILE_NAME = ".env"
DEFAULT_HOME = "~/.dsh-hand"
DEFAULT_KEY_FILE = "~/.dsh-hand/go.key"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_EFFORT = "max"
DEFAULT_BASE_URL = "https://opencode.ai/inference/go/openai/v1"
GO_MODEL_PREFIX = "opencode-go/"  # accepted and stripped: provider-prefixed Go model id
EFFORTS = frozenset({"off", "low", "high", "max"})
USER_AGENT = "hybrid-hands-hand-ext/0.24.0"  # Go asks third-party clients for their own UA
KEY_FILE_MODE = 0o600
# Per-run overlay: dsh applies --patch in argv order, so this wins over hand.patch.yml.
COMPACTION_PATCH_FILE = "compaction.patch.yml"
COMPACTION_ENTRY_ID = "compaction-basic"
COMPACTION_ENTRY_NAME = "@deepseek-ai/dsh-compaction-basic"
# Versions whose env loading and patch keys were read from source (see module docstring).
VERIFIED_VERSIONS = frozenset({"0.2.1-rc.5"})
DOCTOR_TIMEOUT_S = 60
GO_DOCS_URL = "https://opencode.ai/docs/go/"
INSTALL_COMMAND = "npm install -g @deepseek-ai/dsh@latest"

# Browser MCP overlay (see module docstring for the dsh source lines it relies on).
BROWSER_DIR_NAME = "browser"
BROWSER_CLI_RELPATH = "node_modules/@playwright/mcp/cli.js"
BROWSER_STATE_DIR = "ms-playwright"
BROWSER_PATCH_FILE = "browser.patch.json"
BROWSER_OUTPUT_DIR = "browser"
BROWSER_MCP_PLUGIN = "@deepseek-ai/dsh-mcp-client"
BROWSER_MCP_SERVER = "playwright"
BROWSER_MCP_ENTRY_ID = "hand-ext-browser"
BROWSER_COMMAND = "node"
BROWSER_SELECTED = "chromium"
BROWSER_BLOCKED_ORIGINS = ";".join((
    "https://www.tiktok.com", "https://tiktok.com", "https://m.tiktok.com",
    "https://vt.tiktok.com", "https://webcast.tiktok.com",
))
PLAYWRIGHT_BROWSERS_PATH = "PLAYWRIGHT_BROWSERS_PATH"

KEY_ENV = "OPENCODE_GO_API_KEY"  # matches apiKeyEnv in templates/dsh-hand.yml
ENV_HOME = "DSH_HOME"
ENV_PERMISSION = "DSH_PERMISSION_MODE"
# Codex marks its child processes with this env var; nesting a second sandbox-exec below
# seatbelt fails with "sandbox_apply: Operation not permitted" (dsh-sandbox fail-closed).
OUTER_SANDBOX_ENV = "CODEX_SANDBOX"
OUTER_SANDBOX_SEATBELT = "seatbelt"
SANDBOX_READ_ONLY = "read-only"
SANDBOX_WORKSPACE_WRITE = "workspace-write"
SANDBOX_DANGER_FULL_ACCESS = "danger-full-access"
SEATBELT_REASON = "trong sandbox Codex (seatbelt): seatbelt ngoài vẫn giới hạn quyền ghi"
SEATBELT_READ_ONLY_ERROR = (
    "dsh không giữ được read-only bên trong sandbox Codex (CODEX_SANDBOX=seatbelt): "
    "dùng --sandbox workspace-write hoặc giao việc cho hand Claude")
OUTSIDE_SEATBELT_FULL_ACCESS_ERROR = (
    "dsh chỉ chạy danger-full-access khi đã ở trong sandbox Codex (CODEX_SANDBOX=seatbelt)")
META_FILE = "meta.json"
ENV_TELEMETRY = "DSH_TELEMETRY_MODE"
TELEMETRY_OFF = "DISABLED"
ENV_WORKSPACE = "HAND_EXT_DSH_WORKSPACE"
ENV_SESSION = "HAND_EXT_DSH_SESSION"
# OpenCode Go routes by `x-opencode-session` (400 MissingSessionID without it). Discussion
# https://github.com/deepseek-ai/deepseek-harness/discussions/5495 (09-10/2026): explicit `api:`
# routes bypass pi-ai's own header wrapper, a shared static id is slower/costlier, and non-UUID
# or per-request ids fell into a `model_coming_soon` bucket; only a stable RFC 4122 UUID per
# conversation worked consistently. So: one UUID per run, derived from the run id (opaque, not
# dsh's internal session id).
SESSION_NAMESPACE = uuid.UUID("6f0c5d3e-2b1a-5c8e-9f47-0d2e6b1a7c35")


def session_uuid(run_id: str) -> str:
    """Stable RFC 4122 UUID (v5) for one hand run; same run id -> same header value."""
    return str(uuid.uuid5(SESSION_NAMESPACE, run_id))
ENV_MODEL = "HAND_EXT_DSH_MODEL"
ENV_EFFORT = "HAND_EXT_DSH_EFFORT"
ENV_BASE_URL = "HAND_EXT_DSH_BASE_URL"
ENV_USER_AGENT = "HAND_EXT_DSH_USER_AGENT"
STDIN_MARKER = "-"
# Start dsh in another directory without a shell (runner.py always sets cwd to the repo).
CHDIR_EXEC = "import os,sys;os.chdir(sys.argv[1]);os.execvp(sys.argv[2],sys.argv[2:])"

EV_TEXT = "text"
EV_FINAL = "final"
EV_STATUS = "status"
EV_ERROR = "error"
PHASE_STEP_END = "step_end"
PHASE_TURN_END = "turn_end"
REASON_COMPLETED = "completed"
# 429 on Go means the plan limit, except for the
# transient capacity refusal below, which is checked first.
QUOTA_CODES = frozenset({"QUOTA", "ACCOUNT_QUOTA", "RATE_LIMIT"})
REAL_QUOTA_CODES = QUOTA_CODES - {"RATE_LIMIT"}
AUTH_CODES = frozenset({"AUTH", "MISSING_CREDENTIAL", "INVALID_CREDENTIAL"})
QUOTA_TEXT = r"usage limit|quota|insufficient (credit|balance)|GoUsageLimitError"
QUOTA_PATTERN = re.compile(QUOTA_TEXT + r"|\b429\b", re.IGNORECASE)
REAL_QUOTA_PATTERN = re.compile(QUOTA_TEXT, re.IGNORECASE)
AUTH_PATTERN = re.compile(
    r"\b401\b|\b403\b|unauthori[sz]ed|MISSING_CREDENTIAL|INVALID_CREDENTIAL|no API key",
    re.IGNORECASE)


def _path(options: dict, key: str, default: str) -> Path:
    return Path(os.path.expanduser(str((options or {}).get(key) or default)))


def _opt(options: dict, key: str, default: str) -> str:
    return str((options or {}).get(key) or default)


def _int_option(options: dict, key: str, default: int) -> int:
    value = (options or {}).get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} phải là số nguyên, nhận {value!r}")
    return value


def compact_at_option(options: dict) -> int:
    """Auto-compact threshold in tokens; 0 disables the per-run patch."""
    value = _int_option(options, "compact_at", DEFAULT_COMPACT_AT)
    if value < 0:
        raise ValueError(f"compact_at phải >= 0 (0 là tắt tự nén), nhận {value}")
    return value


def context_window_option(options: dict) -> int:
    value = _int_option(options, "context_window", DEFAULT_CONTEXT_WINDOW)
    if value <= 0:
        raise ValueError(f"context_window phải > 0, nhận {value}")
    return value


def compaction_ratio(compact_at: int, context_window: int) -> float:
    if not 0 < compact_at < context_window:
        raise ValueError(
            f"compact_at phải trong (0, {context_window}), nhận {compact_at}")
    return compact_at / context_window


def home_dir(options: dict) -> Path:
    return _path(options, "home", DEFAULT_HOME)


def key_file(options: dict) -> Path:
    return _path(options, "key_file", DEFAULT_KEY_FILE)


def patch_file(options: dict) -> Path:
    return home_dir(options) / PATCH_FILE


def launch_dir(options: dict) -> Path:
    return home_dir(options) / LAUNCH_DIR


def browser_dir(options: dict) -> Path:
    return _path(options, "browser_dir", str(home_dir(options) / BROWSER_DIR_NAME))


def browser_cli(options: dict) -> Path:
    return browser_dir(options) / BROWSER_CLI_RELPATH


def browser_state(options: dict) -> Path:
    return browser_dir(options) / BROWSER_STATE_DIR


def _missing_browser(options: dict) -> List[str]:
    cli, state = browser_cli(options), browser_state(options)
    missing = [] if cli.is_file() else [str(cli)]
    if not state.is_dir():
        missing.append(str(state))
    return missing


def _clean_launch(launch: Path) -> bool:
    """Launch dir exists and holds no `.env` (existence check only, never opened)."""
    return launch.is_dir() and not (launch / ENV_FILE_NAME).exists()


def read_key(path: Path) -> str:
    """The Go key, only at run time; never printed. Raises ValueError when unusable."""
    if not path.is_file():
        raise ValueError(f"thiếu file key Go {path} (xem `hand-ext setup --backend dsh`)")
    if stat.S_IMODE(path.stat().st_mode) != KEY_FILE_MODE:
        raise ValueError(f"file key {path} phải có quyền 600 (chmod 600)")
    key = path.read_text(encoding="utf-8").strip()
    if not key or any(ch.isspace() for ch in key):
        raise ValueError(f"file key {path} phải chứa đúng một key, một dòng")
    return key


def model_id(raw: str) -> str:
    model = raw[len(GO_MODEL_PREFIX):] if raw.startswith(GO_MODEL_PREFIX) else raw
    if not model or "/" in model:
        raise ValueError(f"dsh backend cần model id của OpenCode Go, nhận {raw!r}")
    return model


def in_codex_seatbelt() -> bool:
    """True when dsh runs below Codex's seatbelt sandbox (nested sandbox-exec is refused)."""
    return os.environ.get(OUTER_SANDBOX_ENV) == OUTER_SANDBOX_SEATBELT


def _record_sandbox(spec: RunSpec, mode: str, requested: str, reason: str,
                    refused: bool = False) -> None:
    """Put the effective sandbox mode and why it changed into the run's meta.json."""
    path = spec.run_dir / META_FILE
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path} phải chứa một JSON object")
    meta["sandbox_mode"] = mode
    meta["sandbox_requested"] = requested
    meta["sandbox_reason"] = reason
    if refused:
        meta["sandbox_refused"] = True
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def permission_mode(spec: RunSpec) -> Tuple[str, Optional[str]]:
    """Effective DSH_PERMISSION_MODE plus a reason when seatbelt forces a change.

    Inside Codex's seatbelt, dsh cannot nest another sandbox: workspace-write becomes
    danger-full-access (the outer seatbelt still limits writes) and read-only is refused
    because dsh has no way to guarantee it. Outside seatbelt, danger-full-access is refused:
    the preset exists only for the nested case and dsh must never run unconfined.
    """
    if not in_codex_seatbelt():
        if spec.sandbox == SANDBOX_DANGER_FULL_ACCESS:
            raise ValueError(OUTSIDE_SEATBELT_FULL_ACCESS_ERROR)
        return spec.sandbox, None
    if spec.sandbox == SANDBOX_READ_ONLY:
        _record_sandbox(spec, spec.sandbox, spec.sandbox, SEATBELT_READ_ONLY_ERROR,
                        refused=True)
        raise ValueError(SEATBELT_READ_ONLY_ERROR)
    if spec.sandbox == SANDBOX_WORKSPACE_WRITE:
        return SANDBOX_DANGER_FULL_ACCESS, SEATBELT_REASON
    return spec.sandbox, None


class DshBackend(Backend):
    name = "dsh"
    BLOCKED_ENV = ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "OPENCODE_API_KEY", KEY_ENV,
                   "OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
                   "ANTHROPIC_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                   "GOOGLE_GENERATIVE_AI_API_KEY", "OPENROUTER_API_KEY",
                   "DSH_TELEMETRY_OTLP_URL", "DSH_TOOLS_MODE")

    # ---- setup / doctor -------------------------------------------------
    def setup(self, options: dict) -> List[str]:
        home, launch, patch = home_dir(options), launch_dir(options), patch_file(options)
        launch.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE_PATCH, patch)
        return [
            f"đã tạo {launch} (thư mục rỗng dsh khởi chạy) và chép patch vào {patch}",
            "Người dùng tự làm một lần (agent không làm thay, không đọc key):",
            f"  1. Cài: {INSTALL_COMMAND}",
            f"  2. OpenCode Console > Go: chép API key vào {key_file(options)}"
            f" (một dòng), rồi chmod 600 {key_file(options)}.",
            "  3. Trang Go: TẮT Extra Usage, giữ credit Console = 0 để hết hạn mức thì dừng,"
            f" không trừ tiền ({GO_DOCS_URL}).",
            f"  4. Không tạo {home / ENV_FILE_NAME}; kiểm: hand-ext doctor --backend dsh",
        ]

    def doctor(self, options: dict) -> List[Check]:
        version = self._probe(["--version"], self._probe_dir(options))
        checks = [Check("installed", version is not None,
                        version.strip() if version else f"không thấy dsh: {INSTALL_COMMAND}")]
        if version is None:
            return checks
        checks.append(Check("version_verified", version.strip() in VERIFIED_VERSIONS,
                            "đã đọc mã nguồn bản " + ", ".join(sorted(VERIFIED_VERSIONS))))
        checks.append(self._key_check(key_file(options)))
        seatbelt = self._seatbelt_check(options)
        if seatbelt is not None:
            checks.append(seatbelt)
        checks.extend(self._isolation_checks(options))
        checks.append(self._patch_check(options))
        checks.append(self._browser_check(options))
        return checks

    @staticmethod
    def _seatbelt_check(options: dict) -> Optional[Check]:
        """Read-only cannot be honoured under Codex's seatbelt, so `auto` must skip dsh."""
        if not in_codex_seatbelt():
            return None
        if str(options.get("sandbox", "")) == SANDBOX_READ_ONLY:
            return Check("sandbox", False, SEATBELT_READ_ONLY_ERROR)
        return Check("sandbox", True, "sandbox dùng được trong seatbelt Codex")

    @staticmethod
    def _key_check(path: Path) -> Check:
        if not path.is_file():
            return Check("key_file", False, f"thiếu {path}: người dùng tạo từ OpenCode Console")
        mode = stat.S_IMODE(path.stat().st_mode)
        return Check("key_file", mode == KEY_FILE_MODE, f"{path} quyền {mode:o} (cần 600)")

    @staticmethod
    def _isolation_checks(options: dict) -> List[Check]:
        launch, home = launch_dir(options), home_dir(options)
        launch_ok = _clean_launch(launch)
        home_env = home / ENV_FILE_NAME
        return [
            Check("env_isolation", launch_ok,
                  f"dsh luôn đọc <cwd>/.env; chạy từ {launch} (không có .env)"
                  + ("" if launch_ok else " (thiếu thư mục hoặc có .env: hand-ext setup)")),
            Check("home_env", not home_env.exists(),
                  f"{home_env} " + ("không có" if not home_env.exists() else
                                    "đang có: dsh sẽ nạp, xoá hoặc chuyển đi")),
        ]

    def _patch_check(self, options: dict) -> Check:
        patch = patch_file(options)
        if not patch.is_file():
            return Check("patch", False, f"thiếu {patch}: hand-ext setup --backend dsh")
        dumped = self._probe(["--profile", "headless", "--patch", str(patch), "--dump-config"],
                             self._probe_dir(options), {ENV_HOME: str(home_dir(options))})
        ok = dumped is not None and "opencode-go" in dumped
        return Check("patch", ok, f"{patch} " + ("ghép được (--dump-config)" if ok
                                                 else "không ghép được với --dump-config"))

    @staticmethod
    def _browser_check(options: dict) -> Check:
        missing = _missing_browser(options)
        if missing:
            return Check("browser", False,
                         "chưa cài (tuỳ chọn cho --browser): thiếu " + ", ".join(missing),
                         required=False)
        return Check("browser", True,
                     f"{browser_cli(options)} và {browser_state(options)} có")

    @staticmethod
    def _probe_dir(options: dict) -> Path:
        launch = launch_dir(options)
        return launch if _clean_launch(launch) else Path(tempfile.gettempdir())

    def _probe(self, args: List[str], cwd: Path,
               extra: Optional[Dict[str, str]] = None) -> Optional[str]:
        env = {k: v for k, v in os.environ.items() if k not in self.BLOCKED_ENV}
        env.update(extra or {})
        try:
            done = subprocess.run([bin_for(self.name)] + args, capture_output=True, text=True,
                                  timeout=DOCTOR_TIMEOUT_S, check=False, cwd=str(cwd), env=env)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout if done.returncode == 0 else None

    # ---- run ------------------------------------------------------------
    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        options = spec.options or {}
        launch = launch_dir(options)
        if not _clean_launch(launch):
            raise ValueError(
                f"{launch} phải tồn tại và không có .env (hand-ext setup --backend dsh)")
        if (home_dir(options) / ENV_FILE_NAME).exists():
            raise ValueError(f"{home_dir(options) / ENV_FILE_NAME} tồn tại: dsh sẽ nạp nó")
        effort = spec.effort if spec.effort in EFFORTS else _opt(options, "effort",
                                                                  DEFAULT_EFFORT)
        permission, reason = permission_mode(spec)
        if reason:
            _record_sandbox(spec, permission, spec.sandbox, reason)
        env = {
            KEY_ENV: read_key(key_file(options)),
            ENV_HOME: str(home_dir(options)),
            ENV_TELEMETRY: TELEMETRY_OFF,
            ENV_PERMISSION: permission,
            ENV_WORKSPACE: str(Path(spec.cwd).resolve()),
            ENV_SESSION: session_uuid(spec.run_dir.name),
            ENV_MODEL: model_id(spec.model or _opt(options, "model", DEFAULT_MODEL)),
            ENV_EFFORT: effort,
            ENV_BASE_URL: _opt(options, "base_url", DEFAULT_BASE_URL),
            ENV_USER_AGENT: USER_AGENT,
        }
        argv = [sys.executable, "-c", CHDIR_EXEC, str(launch), bin_for(self.name),
                "--profile", "headless"]
        for patch in self._patches(options, spec):
            argv += ["--patch", str(patch)]
        argv += ["--json", STDIN_MARKER]
        return argv, env, spec.prompt

    @staticmethod
    def _patches(options: dict, spec: RunSpec) -> List[Path]:
        patches = [patch_file(options)]
        if spec.browser:
            patches.append(DshBackend._write_browser_patch(options, spec))
        if compact_at_option(options):
            patches.append(DshBackend._write_compaction_patch(options, spec))
        return patches

    @staticmethod
    def _write_compaction_patch(options: dict, spec: RunSpec) -> Path:
        compact_at = compact_at_option(options)
        ratio = compaction_ratio(compact_at, context_window_option(options))
        spec.run_dir.mkdir(parents=True, exist_ok=True)
        path = spec.run_dir / COMPACTION_PATCH_FILE
        path.write_text(
            "- id: %s\n  name: '%s'\n  config:\n    thresholdRatio: %r\n"
            % (COMPACTION_ENTRY_ID, COMPACTION_ENTRY_NAME, ratio),
            encoding="utf-8")
        return path

    @staticmethod
    def _write_browser_patch(options: dict, spec: RunSpec) -> Path:
        missing = _missing_browser(options)
        if missing:
            raise ValueError(
                "--browser cần Playwright MCP và trình duyệt: thiếu " + ", ".join(missing)
                + " (xem README mục 5.1: cách cài trình duyệt)")
        spec.run_dir.mkdir(parents=True, exist_ok=True)
        output_dir = spec.run_dir / BROWSER_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        args = [
            str(browser_cli(options)), "--headless", "--isolated",
            "--browser", BROWSER_SELECTED,
            "--blocked-origins", BROWSER_BLOCKED_ORIGINS,
            "--output-dir", str(output_dir),
        ]
        entry = {
            "id": BROWSER_MCP_ENTRY_ID,
            "name": BROWSER_MCP_PLUGIN,
            "config": {
                "transport": "stdio",
                "serverName": BROWSER_MCP_SERVER,
                "command": BROWSER_COMMAND,
                "args": args,
                # dsh mcp-client merges this over scrubbedParentEnv(); list only the browser
                # path, never the Go key.
                "env": {PLAYWRIGHT_BROWSERS_PATH: str(browser_state(options))},
                "failOnStartupError": True,
            },
        }
        path = spec.run_dir / BROWSER_PATCH_FILE
        path.write_text(json.dumps([{"insert": [entry]}], ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return path

    def parse_line(self, line: str, state: RunState) -> None:
        line = line.strip()
        if not line.startswith("{"):
            return
        try:
            event = json.loads(line)
        except ValueError:
            return
        kind = event.get("type")
        if kind in (EV_TEXT, EV_FINAL) and event.get("text"):
            state.final_text = event["text"]
        elif kind == EV_STATUS:
            self._status(event, state)
        elif kind == EV_ERROR:
            state.errors.append("error: %s" % event.get("message", ""))

    @staticmethod
    def _status(event: dict, state: RunState) -> None:
        phase = event.get("phase")
        if phase == PHASE_STEP_END:
            usage = event.get("usage") or {}
            cached = int(usage.get("cacheReadTokens", 0))
            state.usage.input += (int(usage.get("inputTokens", 0)) + cached
                                  + int(usage.get("cacheWriteTokens", 0)))
            state.usage.cached_input += cached
            state.usage.output += int(usage.get("outputTokens", 0))
        elif phase == PHASE_TURN_END:
            reason = event.get("reason") or {}
            state.extra["turn_end"] = reason.get("kind", "")
            error = reason.get("error") or {}
            if error:
                state.extra.setdefault("error_codes", []).append(error.get("code", ""))
                state.errors.append("%s: %s" % (error.get("code", "unknown"),
                                                error.get("message", "")))

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        codes = set(state.extra.get("error_codes", []))
        text = "\n".join(state.errors) + "\n" + (stderr_text or "")
        real_quota = bool(codes & REAL_QUOTA_CODES) or bool(REAL_QUOTA_PATTERN.search(text))
        failed = (exit_code != 0 or bool(state.errors)
                  or state.extra.get("turn_end") != REASON_COMPLETED)
        if is_capacity_error(text) and not real_quota:
            if not failed:
                return Status.OK  # recovered through retries; the refusal was only logged
            if CAPACITY_NOTE not in state.errors:
                state.errors.append(CAPACITY_NOTE)
            return Status.FAILED
        if codes & QUOTA_CODES or (exit_code != 0 and QUOTA_PATTERN.search(text)):
            return Status.QUOTA
        if codes & AUTH_CODES or (exit_code != 0 and AUTH_PATTERN.search(text)):
            return Status.NOT_LOGGED_IN
        if exit_code != 0 or state.errors or state.extra.get("turn_end") != REASON_COMPLETED:
            return Status.FAILED
        return Status.OK
