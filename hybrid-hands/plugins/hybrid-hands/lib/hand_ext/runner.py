"""Run one backend CLI: scrubbed env, events/stderr logs, poll loop, token and time caps."""
from __future__ import annotations

import datetime as dt
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, IO, List, Optional, Tuple, TYPE_CHECKING

from .backends.base import Backend, RunSpec, RunState, Status, Usage
from .process_containment import MARKER, SNAPSHOT_INTERVAL
from .constants import EVENTS_FILE, POLL_SECONDS, REPORT_FILE, STDERR_FILE, TERM_GRACE_SECONDS

if TYPE_CHECKING:
    from .run_registry import RunRegistry

_EOF = None  # queue sentinel: stdout closed
RUN_DIR_REMOVED_WARNING = "cảnh báo: thư mục lượt chạy bị xoá trong lúc chạy"


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


def _stamp(line: str) -> str:
    """Add `ts` to an event object; leave non-JSON and non-object lines untouched."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(event, dict):
        return line
    event["ts"] = dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
    return json.dumps(event, ensure_ascii=False) + ("\n" if line.endswith("\n") else "")


def _pump(stream: IO[str], sink: IO[str], lines: "queue.Queue[Optional[str]]") -> None:
    for line in stream:
        sink.write(_stamp(line))
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
           spec: RunSpec, state: RunState, started: float,
           registry: Optional["RunRegistry"] = None, control=None) -> Optional[Status]:
    closed = False
    poll = (lambda: control.poll(proc)) if control is not None else proc.poll
    while not closed or poll() is None:
        if control is not None:
            control.poll(proc)  # snapshot even while stdout remains open
        closed = _drain(backend, lines, state, SNAPSHOT_INTERVAL if control is not None else POLL_SECONDS) or closed
        backend.poll(spec, state)
        if registry is not None:
            registry.tick(state.usage)
        if control is not None and control.cancelled.is_set():
            control.stop(proc)
            return Status.FAILED
        if closed and control is not None and poll() is None:
            try:
                control.wait(proc, timeout=.1)
            except subprocess.TimeoutExpired:
                control.stop(proc)
                return Status.FAILED
        if _over_tokens(spec, state):
            control.stop(proc) if control is not None else _stop(proc)
            return Status.CAPPED
        if time.monotonic() - started > spec.timeout_s:
            control.stop(proc) if control is not None else _stop(proc)
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


def _dir_identity(path: Path) -> Optional[Tuple[int, int]]:
    """Identity of a directory, so a delete-and-recreate is still noticed."""
    if not path.is_dir():
        return None
    info = path.stat()
    return info.st_dev, info.st_ino


def _read_stderr(handle: IO[str]) -> str:
    """Read the child's stderr from the open handle; works after the file is unlinked."""
    try:
        handle.flush()
        handle.seek(0)
        return handle.read()
    except (OSError, ValueError):
        return ""


def _restore_run_dir(run_dir: Path, identity: Optional[Tuple[int, int]]) -> None:
    """Warn once and recreate run_dir when the hand deleted it while the child ran."""
    if identity is not None and _dir_identity(run_dir) == identity:
        return
    print(RUN_DIR_REMOVED_WARNING, file=sys.stderr)
    run_dir.mkdir(parents=True, exist_ok=True)


def run_backend(backend: Backend, spec: RunSpec,
                registry: Optional["RunRegistry"] = None, control=None) -> RunOutcome:
    """Optional owned control supplies spawned/poll/wait/stop and cancelled Event.

    Controlled runs create a session/process group, clean up even on parser/EOF
    failure, and delegate final report settlement to the worker's hooks.
    Legacy callers retain their report behavior and process launch contract.
    """
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    run_dir_identity = _dir_identity(spec.run_dir)
    argv, extra_env, stdin_text = backend.build_command(spec)
    if control is not None:
        extra_env = dict(extra_env, **{MARKER: control.key.invocation_id})
    state = RunState(usage=Usage())
    started = time.monotonic()
    lines: "queue.Queue[Optional[str]]" = queue.Queue()
    stderr_path = spec.run_dir / STDERR_FILE
    with open(spec.run_dir / EVENTS_FILE, "w", encoding="utf-8") as sink, \
            open(stderr_path, "w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, cwd=str(spec.cwd),
                                env=child_env(backend, extra_env),
                                start_new_session=control is not None)
        pump = None
        try:
            if control is not None:
                control.spawned(proc)
            if registry is not None:
                registry.child(proc.pid)
            assert proc.stdout is not None
            pump = threading.Thread(target=_pump, args=(proc.stdout, sink, lines), daemon=True)
            pump.start()
            _write_stdin(proc, stdin_text)
            cap = _watch(backend, proc, lines, spec, state, started, registry, control)
        finally:
            if control is not None:
                control.stop(proc)
            elif proc.poll() is None:
                _stop(proc)
            if pump is not None:
                pump.join(timeout=TERM_GRACE_SECONDS if control is not None else None)
            if pump is None or not pump.is_alive():
                proc.stdout.close()
        _drain(backend, lines, state, 0)
        stderr_text = _read_stderr(err)
    _restore_run_dir(spec.run_dir, run_dir_identity)
    backend.poll(spec, state)
    exit_code = proc.returncode
    status = backend.finalize(spec, state, exit_code, stderr_text)
    if cap is not None:
        status = cap
    elif status is Status.OK and _over_tokens(spec, state):
        status = Status.CAPPED
    report = spec.run_dir / REPORT_FILE
    if control is None and not report.is_file() and state.final_text:
        report.write_text(state.final_text, encoding="utf-8")
    return RunOutcome(status, exit_code, state, time.monotonic() - started, list(state.errors))
