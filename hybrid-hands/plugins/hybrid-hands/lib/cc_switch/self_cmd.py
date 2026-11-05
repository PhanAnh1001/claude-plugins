"""`cc-switch paseo --self`: detach, wait for idle, close the TUI, hand off."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from hh_ps.constants import PARENT_SESSION_ENV

from .constants import (
    EXIT_CONFLICT, EXIT_NOT_FOUND, EXIT_OK, EXIT_USAGE, SELF_ENTRY_NAME,
    SELF_EXIT_POLL_SECONDS, SELF_EXIT_TIMEOUT_SECONDS, SELF_IDLE_SECONDS,
    SELF_MAX_WAIT_MINUTES, SELF_MIN_SLEEP_SECONDS, SELF_WORKER_COMMAND,
)
from .detach import (
    check_duration as _check_duration,
    entry_path as _entry_path,
    log as _log,
    spawn_worker,
    wait_for_idle,
    worker_log_path as self_log_path,
)
from .errors import CcSwitchError
from .models import Transcript
from .paths import short_id
from .paseo_cmd import run_paseo
from .proc import process_alive, select_tui_pid
from .sessions import find_transcript, live_session_cwd, tui_pids


@dataclass(frozen=True)
class SelfPlan:
    session_id: str
    pid: int
    cwd: str
    log_path: Path
    idle_seconds: int
    exit_timeout: int


def _session_from_env() -> str:
    session_id = (os.environ.get(PARENT_SESSION_ENV) or "").strip()
    if not session_id:
        raise CcSwitchError(
            f"Không thấy biến {PARENT_SESSION_ENV} trong tiến trình này.\n"
            "Gợi ý: `--self` chỉ dùng từ bên trong phiên Claude Code TUI; "
            "nếu biết session, dùng `cc-switch paseo --session <sid>`.",
            EXIT_USAGE)
    return session_id


def _session_cwd(transcript: Transcript, session_id: str) -> str:
    cwd = transcript.cwd or live_session_cwd(session_id) or str(Path.cwd())
    try:
        return str(Path(cwd).resolve())
    except (OSError, RuntimeError):
        return cwd


def _print_plan(plan: SelfPlan, dry_run: bool) -> None:
    title = "kế hoạch (dry-run)" if dry_run else "--self"
    print(f"{title}: phiên {short_id(plan.session_id)} — "
          f"TUI pid {plan.pid} — cwd {plan.cwd}")
    print(f"log: {plan.log_path}")
    print(f"bước 1: chờ transcript đứng yên {plan.idle_seconds}s "
          f"(tối đa {SELF_MAX_WAIT_MINUTES} phút)")
    print(f"bước 2: gửi SIGTERM tới pid {plan.pid}, "
          f"chờ tối đa {plan.exit_timeout}s (không SIGKILL)")
    print("bước 3: chạy `cc-switch paseo --session <sid>` để nạp lại hoặc import")
    print("quay lại terminal: cc-switch term")


def _worker_command(plan: SelfPlan) -> List[str]:
    return [
        sys.executable, _entry_path(), SELF_WORKER_COMMAND,
        "--session", plan.session_id,
        "--pid", str(plan.pid),
        "--cwd", plan.cwd,
        "--idle-sec", str(plan.idle_seconds),
        "--exit-timeout", str(plan.exit_timeout),
    ]


def _spawn_worker(plan: SelfPlan) -> subprocess.Popen:
    header = (f"nhận lệnh --self: phiên {short_id(plan.session_id)}, "
              f"TUI pid {plan.pid}, cwd {plan.cwd}, idle {plan.idle_seconds}s, "
              f"exit-timeout {plan.exit_timeout}s")
    return spawn_worker(_worker_command(plan), plan.log_path, plan.cwd, header)


def run_paseo_self(opts) -> int:
    if opts.session:
        raise CcSwitchError(
            "`--self` không đi cùng `--session`: --self tự tìm phiên TUI "
            "đang mở.\nBỏ một trong hai cờ rồi chạy lại.", EXIT_USAGE)
    _check_duration("--idle-sec", opts.idle_sec)
    _check_duration("--exit-timeout", opts.exit_timeout)
    session_id = _session_from_env()
    pids = tui_pids(session_id)
    if not pids:
        raise CcSwitchError(
            f"Phiên {short_id(session_id)} không mở trong terminal "
            "(có thể đã ở Paseo).\n"
            "Gợi ý: mở phiên trong terminal rồi chạy lại, hoặc dùng "
            "`cc-switch paseo --session <sid>`.", EXIT_NOT_FOUND)
    pid = select_tui_pid(pids)
    if pid is None:
        pid_text = ", ".join(str(item) for item in pids)
        raise CcSwitchError(
            f"Phiên {short_id(session_id)} đang mở ở nhiều terminal "
            f"(pid {pid_text}), nhưng không xác định được pid nào là tổ tiên "
            "của tiến trình hiện tại.\n"
            "Gợi ý: đóng bớt cửa sổ terminal của phiên này rồi chạy lại.",
            EXIT_CONFLICT)

    transcript = find_transcript(session_id)
    if transcript is None:
        raise CcSwitchError(
            f"Không tìm thấy transcript cho phiên {short_id(session_id)}.\n"
            "Gợi ý: kiểm tra `cc-switch status`, hoặc dùng "
            "`cc-switch paseo --session <sid>` khi TUI đã đóng.",
            EXIT_NOT_FOUND)
    cwd = _session_cwd(transcript, session_id)
    if not Path(cwd).is_dir():
        raise CcSwitchError(
            f"Thư mục làm việc của phiên không còn tồn tại: {cwd}",
            EXIT_NOT_FOUND)

    plan = SelfPlan(
        session_id=session_id, pid=pid, cwd=cwd,
        log_path=self_log_path(session_id),
        idle_seconds=opts.idle_sec, exit_timeout=opts.exit_timeout,
    )
    _print_plan(plan, opts.dry_run)
    if opts.dry_run:
        return EXIT_OK

    worker = _spawn_worker(plan)
    print(f"Đã tách tiến trình nền pid {worker.pid}; TUI pid {plan.pid} "
          f"sẽ nhận SIGTERM sau khi transcript đứng yên "
          f"{plan.idle_seconds}s.")
    print("Đừng gõ hay nhấn Enter cho tới khi TUI tự đóng.")
    return EXIT_OK


def build_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{SELF_ENTRY_NAME} {SELF_WORKER_COMMAND}",
        description="(nội bộ) tiến trình nền của `cc-switch paseo --self`.")
    parser.add_argument("--session", required=True, help="sessionId Claude")
    parser.add_argument("--pid", type=int, required=True,
                        help="pid TUI cần đóng bằng SIGTERM")
    parser.add_argument("--cwd", required=True, help="cwd của phiên")
    parser.add_argument("--idle-sec", type=int, default=SELF_IDLE_SECONDS,
                        help=f"chờ transcript đứng yên (mặc định "
                             f"{SELF_IDLE_SECONDS})")
    parser.add_argument("--exit-timeout", type=int,
                        default=SELF_EXIT_TIMEOUT_SECONDS,
                        help=f"chờ TUI thoát sau SIGTERM (mặc định "
                             f"{SELF_EXIT_TIMEOUT_SECONDS})")
    return parser


def wait_for_exit(pid: int, timeout_seconds: float,
                  poll_seconds: float = SELF_EXIT_POLL_SECONDS) -> bool:
    """True when `pid` is gone (a zombie counts as gone), within the timeout."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        if not process_alive(pid):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(max(min(poll_seconds, remaining), SELF_MIN_SLEEP_SECONDS))


def _close_tui(session_id: str, pid: int, exit_timeout: int) -> int:
    if pid not in tui_pids(session_id):
        if not process_alive(pid):
            _log(f"TUI pid {pid} đã thoát trước khi đóng; không gửi tín hiệu")
            return EXIT_OK
        _log(f"pid {pid} còn sống nhưng không còn là TUI của phiên "
             f"{short_id(session_id)}; không gửi tín hiệu")
        return EXIT_CONFLICT
    _log(f"gửi SIGTERM tới TUI pid {pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _log("TUI đã thoát trước khi nhận SIGTERM")
        return EXIT_OK
    except OSError as exc:
        _log(f"không gửi được SIGTERM: {exc}")
        return EXIT_CONFLICT
    if not wait_for_exit(pid, exit_timeout):
        _log(f"TUI pid {pid} chưa thoát sau {exit_timeout}s; "
             "không SIGKILL, bỏ cuộc")
        return EXIT_CONFLICT
    _log(f"TUI pid {pid} đã thoát")
    return EXIT_OK


def run_self_worker(opts) -> int:
    session_id = opts.session
    pid = opts.pid
    cwd = opts.cwd
    _check_duration("--idle-sec", opts.idle_sec)
    _check_duration("--exit-timeout", opts.exit_timeout)
    _log(f"bắt đầu: phiên {short_id(session_id)}, TUI pid {pid}, cwd {cwd}")

    transcript = find_transcript(session_id)
    if transcript is None:
        _log("không tìm thấy transcript; bỏ cuộc")
        return EXIT_NOT_FOUND
    _log(f"chờ transcript {transcript.path} đứng yên {opts.idle_sec}s "
         f"(tối đa {SELF_MAX_WAIT_MINUTES} phút)")
    if not wait_for_idle(transcript.path, opts.idle_sec):
        _log("transcript vẫn đang ghi; bỏ cuộc")
        return EXIT_NOT_FOUND
    _log("transcript đã đứng yên")

    code = _close_tui(session_id, pid, opts.exit_timeout)
    if code != EXIT_OK:
        return code
    try:
        os.chdir(cwd)
    except OSError as exc:
        _log(f"không chuyển được vào cwd {cwd}: {exc}")
        return EXIT_NOT_FOUND

    _log("chạy luồng `cc-switch paseo --session`")
    try:
        result = run_paseo(SimpleNamespace(session=session_id, dry_run=False))
    except CcSwitchError as exc:
        _log(f"lỗi paseo: {exc.message}")
        return exc.code
    _log(f"xong (mã {result})")
    return result
