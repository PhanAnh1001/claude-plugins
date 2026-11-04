"""Run one backend CLI: scrubbed env, events/stderr logs, poll loop, token and time caps."""
from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, IO, List, Optional

from .backends.base import Backend, RunSpec, RunState, Status, Usage
from .constants import EVENTS_FILE, POLL_SECONDS, REPORT_FILE, STDERR_FILE, TERM_GRACE_SECONDS

_EOF = None  # queue sentinel: stdout closed


@dataclass
class RunOutcome:
    status: Status
    exit_code: Optional[int]
    state: RunState
    seconds: float
    errors: List[str] = field(default_factory=list)


def child_env(backend: Backend, extra: Dict[str, str]) -> Dict[str, str]:
    """os.environ minus the backend's BLOCKED_ENV (API keys), plus backend extras."""
    env = {k: v for k, v in os.environ.items() if k not in backend.BLOCKED_ENV}
    env.update(extra)
    return env


def _pump(stream: IO[str], sink: IO[str], lines: "queue.Queue[Optional[str]]") -> None:
    for line in stream:
        sink.write(line)
        sink.flush()
        lines.put(line)
    lines.put(_EOF)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _over_tokens(spec: RunSpec, state: RunState) -> bool:
    return spec.max_tokens is not None and state.usage.total() > spec.max_tokens


def _drain(backend: Backend, lines: "queue.Queue[Optional[str]]", state: RunState,
           wait_s: float) -> bool:
    """Feed queued lines to parse_line; return True once stdout has closed."""
    deadline = time.monotonic() + wait_s
    while True:
        remaining = deadline - time.monotonic()
        try:
            line = lines.get(timeout=max(remaining, 0)) if remaining > 0 else lines.get_nowait()
        except queue.Empty:
            return False
        if line is _EOF:
            return True
        backend.parse_line(line.rstrip("\n"), state)


def _watch(backend: Backend, proc: subprocess.Popen, lines: "queue.Queue[Optional[str]]",
           spec: RunSpec, state: RunState, started: float) -> Optional[Status]:
    closed = False
    while not closed or proc.poll() is None:
        closed = _drain(backend, lines, state, POLL_SECONDS) or closed
        backend.poll(spec, state)
        if _over_tokens(spec, state):
            _stop(proc)
            return Status.CAPPED
        if time.monotonic() - started > spec.timeout_s:
            _stop(proc)
            return Status.TIMEOUT
    return None


def _write_stdin(proc: subprocess.Popen, text: Optional[str]) -> None:
    if proc.stdin is None:
        return
    try:
        if text:
            proc.stdin.write(text)
        proc.stdin.close()
    except BrokenPipeError:
        pass


def run_backend(backend: Backend, spec: RunSpec) -> RunOutcome:
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    argv, extra_env, stdin_text = backend.build_command(spec)
    state = RunState(usage=Usage())
    started = time.monotonic()
    lines: "queue.Queue[Optional[str]]" = queue.Queue()
    stderr_path = spec.run_dir / STDERR_FILE
    with open(spec.run_dir / EVENTS_FILE, "w", encoding="utf-8") as sink, \
            open(stderr_path, "w", encoding="utf-8") as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, cwd=str(spec.cwd),
                                env=child_env(backend, extra_env))
        assert proc.stdout is not None
        pump = threading.Thread(target=_pump, args=(proc.stdout, sink, lines), daemon=True)
        pump.start()
        _write_stdin(proc, stdin_text)
        cap = _watch(backend, proc, lines, spec, state, started)
        pump.join()
        _drain(backend, lines, state, 0)
    backend.poll(spec, state)
    exit_code = proc.returncode
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    status = backend.finalize(spec, state, exit_code, stderr_text)
    if cap is not None:
        status = cap
    elif status is Status.OK and _over_tokens(spec, state):
        status = Status.CAPPED
    report = spec.run_dir / REPORT_FILE
    if not report.is_file() and state.final_text:
        report.write_text(state.final_text, encoding="utf-8")
    return RunOutcome(status, exit_code, state, time.monotonic() - started, list(state.errors))
