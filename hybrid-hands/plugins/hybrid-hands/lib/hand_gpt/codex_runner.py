"""Spawn `codex exec --json`, stream events, meter USD from the rollout, enforce caps."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, List, Optional

from .constants import (
    CODEX_BIN_ENV, CODEX_DEFAULT_BIN, EVENTS_FILE, FLEX_REJECT_MARKERS, POLL_SECONDS,
    REPORT_FILE, STANDARD_TIER, STDERR_FILE, TERM_GRACE_SECONDS, Status,
)
from .pricing import Tokens, cost_for_call
from .rollout import RolloutMeter, find_rollout

EVENT_THREAD_STARTED = "thread.started"
EVENT_TURN_COMPLETED = "turn.completed"
EVENT_TURN_FAILED = "turn.failed"
EVENT_ERROR = "error"


@dataclass
class RunSpec:
    prompt: str
    cwd: Path
    run_dir: Path
    codex_home: Path
    model: str
    tier: str
    effort: str
    sandbox: str
    max_usd: float
    timeout_s: float
    prices: dict


@dataclass
class RunResult:
    status: Status
    exit_code: Optional[int]
    tokens: Tokens
    usd: float
    seconds: float
    thread_id: str = ""
    errors: List[str] = field(default_factory=list)
    report_path: Optional[Path] = None


def codex_bin() -> str:
    return os.environ.get(CODEX_BIN_ENV) or shutil.which(CODEX_DEFAULT_BIN) or CODEX_DEFAULT_BIN


def build_command(spec: RunSpec) -> List[str]:
    cmd = [
        codex_bin(), "exec", "--json",
        "-o", str(spec.run_dir / REPORT_FILE),
        "-C", str(spec.cwd),
        "-s", spec.sandbox,
        "-m", spec.model,
    ]
    if spec.tier != STANDARD_TIER:
        cmd += ["-c", f'service_tier="{spec.tier}"']
    cmd += ["-c", f'model_reasoning_effort="{spec.effort}"', "-"]
    return cmd


class _EventReader(threading.Thread):
    """Copies codex stdout to events.jsonl and extracts thread id, usage, errors."""

    def __init__(self, stream: IO[str], sink: IO[str]) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.sink = sink
        self.thread_id = ""
        self.exec_tokens = Tokens()
        self.errors: List[str] = []

    def run(self) -> None:
        for line in self.stream:
            self.sink.write(line)
            self.sink.flush()
            self._handle(line)

    def _handle(self, line: str) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind == EVENT_THREAD_STARTED:
            self.thread_id = str(event.get("thread_id", ""))
        elif kind == EVENT_TURN_COMPLETED:
            self.exec_tokens = self.exec_tokens.plus(Tokens.from_usage(event.get("usage") or {}))
        elif kind == EVENT_TURN_FAILED:
            self.errors.append(_message((event.get("error") or {})))
        elif kind == EVENT_ERROR:
            self.errors.append(_message(event))


def _message(obj: dict) -> str:
    return str(obj.get("message", obj))


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def is_flex_rejection(errors: List[str]) -> bool:
    text = " ".join(errors).lower()
    return any(marker in text for marker in FLEX_REJECT_MARKERS)


def _watch(proc: subprocess.Popen, reader: _EventReader, meter: RolloutMeter,
           spec: RunSpec, started: float) -> Optional[Status]:
    """Poll until codex exits; return CAPPED/TIMEOUT if a cap stopped it."""
    while proc.poll() is None:
        if meter.path is None and reader.thread_id:
            found = find_rollout(spec.codex_home, reader.thread_id)
            if found:
                meter.attach(found)
        if meter.poll() > spec.max_usd:
            _stop(proc)
            return Status.CAPPED
        if time.monotonic() - started > spec.timeout_s:
            _stop(proc)
            return Status.TIMEOUT
        time.sleep(POLL_SECONDS)
    return None


def _final_status(cap: Optional[Status], code: Optional[int], errors: List[str],
                  tier: str, usd: float, max_usd: float) -> Status:
    if cap is not None:
        return cap
    if usd > max_usd:
        return Status.CAPPED
    if code == 0 and not errors:
        return Status.OK
    if tier != STANDARD_TIER and is_flex_rejection(errors):
        return Status.FLEX_REJECTED
    return Status.FAILED


def run_codex(spec: RunSpec) -> RunResult:
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CODEX_HOME=str(spec.codex_home))
    meter = RolloutMeter(spec.prices)
    started = time.monotonic()
    with open(spec.run_dir / EVENTS_FILE, "w", encoding="utf-8") as sink, \
            open(spec.run_dir / STDERR_FILE, "w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            build_command(spec), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=err, text=True, env=env, cwd=str(spec.cwd),
        )
        reader = _EventReader(proc.stdout, sink)
        reader.start()
        assert proc.stdin is not None
        try:
            proc.stdin.write(spec.prompt)
            proc.stdin.close()
        except BrokenPipeError:
            pass
        cap = _watch(proc, reader, meter, spec, started)
        reader.join()
    if meter.path is None and reader.thread_id:
        found = find_rollout(spec.codex_home, reader.thread_id)
        if found:
            meter.attach(found)
    meter.poll()
    tokens, usd = (meter.total, meter.usd) if meter.events else (
        reader.exec_tokens, cost_for_call(reader.exec_tokens, spec.prices))
    status = _final_status(cap, proc.returncode, reader.errors, spec.tier, usd, spec.max_usd)
    report = spec.run_dir / REPORT_FILE
    return RunResult(
        status=status, exit_code=proc.returncode, tokens=tokens, usd=usd,
        seconds=time.monotonic() - started, thread_id=reader.thread_id,
        errors=reader.errors, report_path=report if report.is_file() else None,
    )
