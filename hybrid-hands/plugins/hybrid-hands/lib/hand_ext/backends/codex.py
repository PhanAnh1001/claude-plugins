"""codex backend: `codex exec --json` on a ChatGPT subscription login (never an API key).

Ported from hand_gpt/codex_runner.py and rollout.py; USD metering replaced by the
rollout's token_count totals and rate_limits (windows identified by window_minutes).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import codex_config as cc
from .base import Backend, Check, Quota, RunSpec, RunState, Status, Usage, bin_for
from .sandbox import (META_FILE, OUTER_SANDBOX_ENV, OUTER_SANDBOX_SEATBELT,
                      SANDBOX_DANGER_FULL_ACCESS, SANDBOX_READ_ONLY,
                      SANDBOX_WORKSPACE_WRITE, in_codex_seatbelt, record_sandbox)

NAME = "codex"
SESSIONS_DIR = "sessions"
REPORT_FILE = "report.md"
LOGIN_COMMAND = "CODEX_HOME={home} codex login --device-auth"
CHECK_TIMEOUT_S = 30
FULL_PERCENT = 100.0
EVENT_THREAD_STARTED = "thread.started"
EVENT_TURN_FAILED = "turn.failed"
EVENT_ERROR = "error"
TOKEN_COUNT_TYPE = "token_count"
WINDOWS = ("primary", "secondary")
WINDOW_LABELS = {"primary": "5h", "secondary": "7d"}
WINDOW_MINUTES = {300: "5h", 10080: "7d"}
WINDOWS_EXTRA = "windows"  # RunState.extra: both windows, kept separately for the ledger
QUOTA_MARKERS = ("hit your usage limit", "rate_limit_reached", "usage_limit_reached",
                 "credits_depleted")
LOGIN_MARKERS = ("not logged in", "login required", "please log in", "codex login")
DEFAULT_HOME = "~/.codex-hand"
SEATBELT_REASON = "trong sandbox Codex (seatbelt): seatbelt ngoài vẫn giới hạn quyền ghi"
SEATBELT_READ_ONLY_ERROR = (
    "codex không giữ được read-only bên trong sandbox Codex (CODEX_SANDBOX=seatbelt): "
    "dùng --sandbox workspace-write hoặc giao việc cho hand Claude")


def sandbox_mode(spec: RunSpec) -> str:
    """Effective `-s` mode: Codex cannot nest its seatbelt inside Codex's own seatbelt.

    Inside seatbelt, workspace-write becomes danger-full-access (the outer seatbelt still
    limits writes); read-only is refused because Codex has no way to guarantee it. Outside
    seatbelt the requested mode is unchanged.
    """
    if not in_codex_seatbelt():
        return spec.sandbox
    if spec.sandbox == SANDBOX_READ_ONLY:
        record_sandbox(spec, spec.sandbox, spec.sandbox, SEATBELT_READ_ONLY_ERROR,
                       refused=True)
        raise ValueError(SEATBELT_READ_ONLY_ERROR)
    if spec.sandbox == SANDBOX_WORKSPACE_WRITE:
        record_sandbox(spec, SANDBOX_DANGER_FULL_ACCESS, spec.sandbox, SEATBELT_REASON)
        return SANDBOX_DANGER_FULL_ACCESS
    return spec.sandbox


def home_dir(options: dict) -> Path:
    """The hand's own CODEX_HOME; never the default ~/.codex account."""
    return Path(os.path.expanduser(str((options or {}).get("home") or DEFAULT_HOME)))


def _home(options: dict) -> Path:
    return home_dir(options)


def _iso_reset(value: object) -> Optional[str]:
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat(timespec="seconds")
    return str(value) if value else None


def windows_from_rate_limits(limits: dict) -> Dict[str, Optional[dict]]:
    """Keep each duration separately; some plans have only a weekly primary window."""
    limits = limits if isinstance(limits, dict) else {}
    windows: Dict[str, Optional[dict]] = {"5h": None, "7d": None}
    for name in WINDOWS:
        window = limits.get(name)
        if not isinstance(window, dict) or window.get("used_percent") is None:
            continue
        duration = window.get("window_minutes")
        # Older rollouts omitted the duration; preserve their established slot mapping.
        label = WINDOW_LABELS[name] if duration is None else WINDOW_MINUTES.get(duration)
        if label is None:
            continue
        try:
            used = float(window["used_percent"])
        except (TypeError, ValueError):
            continue
        windows[label] = {"used_percent": used,
                          "resets_at": _iso_reset(window.get("resets_at"))}
    return windows


def quota_from_rate_limits(limits: dict) -> Quota:
    """used_percent = max of windows; resets_at/window of the window that is fullest."""
    quota = Quota()
    for name in WINDOWS:
        window = limits.get(name)
        if not isinstance(window, dict) or window.get("used_percent") is None:
            continue
        used = float(window["used_percent"])
        if quota.used_percent is None or used >= quota.used_percent:
            quota.used_percent = used
            quota.resets_at = _iso_reset(window.get("resets_at"))
            quota.window = name
    quota.exhausted = bool(limits.get("rate_limit_reached_type")) or (
        quota.used_percent is not None and quota.used_percent >= FULL_PERCENT)
    return quota


def _has_marker(text: str, markers: Tuple[str, ...]) -> bool:
    low = text.lower()
    return any(m in low for m in markers)


class CodexBackend(Backend):
    name = NAME
    BLOCKED_ENV = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_API_KEY", "OPENAI_ORG_ID",
                   "OPENAI_ORGANIZATION", "OPENAI_PROJECT_ID")

    def _keys(self, options: dict) -> Dict[str, str]:
        keys = {"model": str(options.get("model", "")),
                "model_reasoning_effort": str(options.get("effort", "")),
                "sandbox_mode": str(options.get("sandbox", ""))}
        return {k: v for k, v in keys.items() if v}

    def setup(self, options: dict) -> List[str]:
        home = _home(options)
        changed = cc.write_config(home, self._keys(options))
        return [f"{'đã ghi' if changed else 'không đổi'}: {home / cc.CONFIG_FILE}",
                "Đăng nhập gói ChatGPT (tự chạy trong terminal riêng):",
                f"  {LOGIN_COMMAND.format(home=home)}"]

    def _run_check(self, args: List[str], home: Path) -> Tuple[bool, str]:
        env = {k: v for k, v in os.environ.items() if k not in self.BLOCKED_ENV}
        env["CODEX_HOME"] = str(home)
        try:
            out = subprocess.run([bin_for(NAME)] + args, capture_output=True, text=True,
                                 timeout=CHECK_TIMEOUT_S, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"không chạy được: {exc.__class__.__name__}"
        first = (out.stdout + out.stderr).strip().splitlines()
        return out.returncode == 0, first[0] if first else ""

    def doctor(self, options: dict) -> List[Check]:
        home = _home(options)
        ok, version = self._run_check(["--version"], home)
        checks = [Check("cài đặt", ok, version or "không đọc được version")]
        mode = cc.auth_mode(home)
        hint = LOGIN_COMMAND.format(home=home)
        if mode == cc.SUBSCRIPTION_AUTH_MODE:
            checks.append(Check("đăng nhập gói", True, "chatgpt"))
        elif mode == cc.API_KEY_AUTH_MODE:
            checks.append(Check("đăng nhập gói", False,
                                f"đang dùng API key (tính tiền) - đăng nhập lại gói: {hint}"))
        else:
            checks.append(Check("đăng nhập gói", False, f"chưa đăng nhập ({mode or 'không có auth'}); {hint}"))
        path = home / cc.CONFIG_FILE
        current = cc.top_level_values(path.read_text(encoding="utf-8") if path.is_file() else "")
        wrong = [k for k, v in self._keys(options).items() if current.get(k) != v]
        wrong += [k for k in cc.REMOVED_KEYS if k in current]
        checks.append(Check("cấu hình", not wrong,
                            str(path) if not wrong else f"lệch {wrong}; chạy `hand-ext setup --backend codex`"))
        return checks

    def build_command(self, spec: RunSpec) -> Tuple[List[str], Dict[str, str], Optional[str]]:
        argv = [bin_for(NAME), "exec", "--json", "--skip-git-repo-check",
                "-C", str(spec.cwd), "-m", spec.model,
                "-c", f'model_reasoning_effort="{spec.effort}"',
                "-s", sandbox_mode(spec), "-o", str(spec.run_dir / REPORT_FILE), "-"]
        return argv, {"CODEX_HOME": str(_home(spec.options))}, spec.prompt

    def parse_line(self, line: str, state: RunState) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind == EVENT_THREAD_STARTED:
            state.extra["thread_id"] = str(event.get("thread_id", ""))
        elif kind == EVENT_TURN_FAILED:
            state.errors.append(str((event.get("error") or {}).get("message", event)))
        elif kind == EVENT_ERROR:
            state.errors.append(str(event.get("message", event)))

    def _rollout(self, spec: RunSpec, state: RunState) -> Optional[Path]:
        found = state.extra.get("rollout")
        if found:
            return Path(found)
        tid = state.extra.get("thread_id")
        sessions = _home(spec.options) / SESSIONS_DIR
        if not tid or not sessions.is_dir():
            return None
        matches = sorted(sessions.rglob(f"rollout-*{tid}.jsonl"))
        if not matches:
            return None
        state.extra["rollout"] = str(matches[-1])
        return matches[-1]

    def poll(self, spec: RunSpec, state: RunState) -> None:
        path = self._rollout(spec, state)
        if path is None or not path.is_file():
            return
        offset = int(state.extra.get("rollout_offset", 0))
        with open(path, "rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        state.extra["rollout_offset"] = offset + end + 1
        for raw in chunk[: end + 1].splitlines():
            self._consume(raw, state)

    def _consume(self, raw: bytes, state: RunState) -> None:
        try:
            record = json.loads(raw)
        except ValueError:
            return
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict) or payload.get("type") != TOKEN_COUNT_TYPE:
            return
        total = (payload.get("info") or {}).get("total_token_usage")
        if isinstance(total, dict):
            state.usage = Usage(input=int(total.get("input_tokens", 0) or 0),
                                cached_input=int(total.get("cached_input_tokens", 0) or 0),
                                output=int(total.get("output_tokens", 0) or 0))
        limits = payload.get("rate_limits")
        if isinstance(limits, dict):
            state.quota = quota_from_rate_limits(limits)
            state.extra[WINDOWS_EXTRA] = windows_from_rate_limits(limits)
            if limits.get("plan_type"):
                state.extra["plan_type"] = str(limits["plan_type"])

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        report = spec.run_dir / REPORT_FILE
        if report.is_file():
            state.final_text = report.read_text(encoding="utf-8")
        if exit_code == 0 and not state.errors:
            return Status.OK  # finished; quota.exhausted (if set) is still recorded by the core
        text = " ".join(state.errors) + " " + stderr_text
        if _has_marker(text, QUOTA_MARKERS) or (state.quota is not None and state.quota.exhausted):
            if state.quota is None:
                state.quota = Quota()
            state.quota.exhausted = True
            return Status.QUOTA
        if _has_marker(text, LOGIN_MARKERS):
            return Status.NOT_LOGGED_IN
        return Status.FAILED
