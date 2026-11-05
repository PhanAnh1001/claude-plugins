"""`cc-switch term --self`: open a Terminal window for a Paseo-held session."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from hh_ps.constants import PARENT_SESSION_ENV

from .agents import by_session, load_agents, preferred_agent
from .constants import (
    EXIT_CONFLICT, EXIT_NOT_FOUND, EXIT_OK, EXIT_USAGE, HANDOFF_SUBDIR,
    MACOS_PLATFORM, OPEN_BIN, OPEN_TIMEOUT_SECONDS, SELF_ENTRY_NAME,
    SELF_IDLE_SECONDS, SELF_MAX_WAIT_MINUTES, SHORT_ERROR_MAX_CHARS,
    TERM_APP_CHOICES, TERM_APP_DEFAULT, TERM_COMMAND_FILE_PREFIX,
    TERM_COMMAND_FILE_SUFFIX, TERM_COMMAND_SHEBANG, TERM_WINDOW_COMMAND,
    TERM_WORKER_COMMAND,
)
from .detach import (
    check_duration, entry_path, log, spawn_worker, wait_for_idle,
    worker_log_path,
)
from .errors import CcSwitchError
from .models import Agent
from .paths import short_id, state_dir
from .sessions import find_transcript, tui_pids


@dataclass(frozen=True)
class TermSelfPlan:
    session_id: str
    agent_id: str
    cwd: str
    app: str
    log_path: Path
    idle_seconds: int


def _session_from_env() -> str:
    session_id = (os.environ.get(PARENT_SESSION_ENV) or "").strip()
    if not session_id:
        raise CcSwitchError(
            f"Không thấy biến {PARENT_SESSION_ENV} trong tiến trình này.\n"
            "Gợi ý: `--self` chỉ dùng từ bên trong phiên Claude Code do Paseo "
            "giữ; nếu biết session, dùng `cc-switch term --session <sid>`.",
            EXIT_USAGE)
    return session_id


def _agent_for_session(session_id: str) -> Agent:
    matches = by_session(load_agents(), session_id)
    if not matches:
        raise CcSwitchError(
            f"Phiên {short_id(session_id)} không do Paseo giữ.\n"
            "Gợi ý: nếu phiên đang mở trong terminal, dùng "
            "`cc-switch term --session <sid>`; xem agent bằng `cc-switch status`.",
            EXIT_NOT_FOUND)
    return preferred_agent(matches)


def _agent_cwd(agent: Agent) -> str:
    if not agent.cwd:
        raise CcSwitchError(
            f"Agent {short_id(agent.id)} không có thư mục làm việc.",
            EXIT_NOT_FOUND)
    try:
        cwd = str(Path(agent.cwd).resolve())
    except (OSError, RuntimeError):
        cwd = agent.cwd
    if not Path(cwd).is_dir():
        raise CcSwitchError(
            f"Thư mục làm việc của agent không còn tồn tại: {cwd}",
            EXIT_NOT_FOUND)
    return cwd


def _live_tui_error(session_id: str, pids: List[int]) -> CcSwitchError:
    pid_text = ", ".join(str(pid) for pid in pids)
    return CcSwitchError(
        f"Phiên {short_id(session_id)} đã mở trong terminal (pid {pid_text}).\n"
        "Gợi ý: thoát Claude Code (/exit) rồi chạy lại, hoặc dùng "
        "`cc-switch paseo` nếu muốn chuyển sang Paseo.",
        EXIT_CONFLICT)


def _shell_command(session_id: str, cwd: str) -> str:
    return TERM_WINDOW_COMMAND.format(
        cwd=shlex.quote(cwd), entry=shlex.quote(entry_path()),
        session=shlex.quote(session_id))


def command_file_path(session_id: str) -> Path:
    name = f"{TERM_COMMAND_FILE_PREFIX}{short_id(session_id)}{TERM_COMMAND_FILE_SUFFIX}"
    return state_dir() / HANDOFF_SUBDIR / name


def _write_command_file(session_id: str, shell_command: str) -> Path:
    """A private `.command` script the terminal app runs in a new window."""
    path = command_file_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{TERM_COMMAND_SHEBANG}\n{shell_command}\n",
                    encoding="utf-8")
    path.chmod(0o700)
    return path


def _open_argv(app: str, script: Path) -> List[str]:
    return [OPEN_BIN, "-a", app, str(script)]


def _print_plan(plan: TermSelfPlan) -> None:
    print(f"kế hoạch (dry-run): phiên {short_id(plan.session_id)} — "
          f"agent {short_id(plan.agent_id)} — app {plan.app}")
    print(f"cwd: {plan.cwd}")
    print(f"log: {plan.log_path}")
    print(f"lệnh trong cửa sổ: {_shell_command(plan.session_id, plan.cwd)}")
    print(f"bước 1: chờ transcript đứng yên {plan.idle_seconds}s "
          f"(tối đa {SELF_MAX_WAIT_MINUTES} phút)")
    print("bước 2: kiểm lại không có TUI sống cho phiên")
    print(f"bước 3: ghi lệnh trên vào file .command rồi `open -a {plan.app}` file đó")


def _worker_command(plan: TermSelfPlan) -> List[str]:
    return [
        sys.executable, entry_path(), TERM_WORKER_COMMAND,
        "--session", plan.session_id,
        "--cwd", plan.cwd,
        "--idle-sec", str(plan.idle_seconds),
        "--app", plan.app,
    ]


def _spawn_worker(plan: TermSelfPlan) -> subprocess.Popen:
    header = (f"nhận lệnh term --self: phiên {short_id(plan.session_id)}, "
              f"agent {short_id(plan.agent_id)}, cwd {plan.cwd}, "
              f"app {plan.app}, idle {plan.idle_seconds}s")
    return spawn_worker(_worker_command(plan), plan.log_path, plan.cwd, header)


def run_term_self(opts) -> int:
    if opts.agent:
        raise CcSwitchError(
            "`--self` không đi cùng `--agent`: --self tự tìm agent Paseo "
            "theo session.\nBỏ một trong hai cờ rồi chạy lại.", EXIT_USAGE)
    if opts.session:
        raise CcSwitchError(
            "`--self` không đi cùng `--session`: --self tự lấy session từ "
            "biến môi trường.\nBỏ một trong hai cờ rồi chạy lại.", EXIT_USAGE)
    if opts.extra:
        raise CcSwitchError(
            "`--self` không nhận đối số sau `--`.\n"
            "Bỏ phần sau `--` rồi chạy lại.", EXIT_USAGE)
    check_duration("--idle-sec", opts.idle_sec)
    if opts.app not in TERM_APP_CHOICES:
        raise CcSwitchError(
            f"App không hỗ trợ: {opts.app}. Chọn {', '.join(TERM_APP_CHOICES)}.",
            EXIT_USAGE)

    session_id = _session_from_env()
    pids = tui_pids(session_id)
    if pids:
        raise _live_tui_error(session_id, pids)
    agent = _agent_for_session(session_id)
    if sys.platform != MACOS_PLATFORM:
        raise CcSwitchError(
            "`term --self` chỉ hỗ trợ macOS vì cần mở cửa sổ Terminal.app "
            "hoặc iTerm.\n"
            f"Hệ điều hành hiện tại: {sys.platform}.", EXIT_USAGE)
    cwd = _agent_cwd(agent)

    plan = TermSelfPlan(
        session_id=session_id, agent_id=agent.id, cwd=cwd, app=opts.app,
        log_path=worker_log_path(session_id), idle_seconds=opts.idle_sec,
    )
    if opts.dry_run:
        _print_plan(plan)
        return EXIT_OK

    worker = _spawn_worker(plan)
    print(f"Đã tách tiến trình nền pid {worker.pid}; cửa sổ {plan.app} sẽ mở "
          "sau khi lượt này xong.")
    print(f"log: {plan.log_path}")
    print(f"Đừng gửi tin cho agent {short_id(plan.agent_id)} từ Paseo cho tới "
          "khi chạy `/to-paseo` hoặc `cc-switch paseo`.")
    return EXIT_OK


def build_term_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{SELF_ENTRY_NAME} {TERM_WORKER_COMMAND}",
        description="(nội bộ) tiến trình nền của `cc-switch term --self`.")
    parser.add_argument("--session", required=True, help="sessionId Claude")
    parser.add_argument("--cwd", required=True,
                        help="cwd của phiên, dùng cho lệnh trong cửa sổ")
    parser.add_argument("--idle-sec", type=int, default=SELF_IDLE_SECONDS,
                        help=f"chờ transcript đứng yên (mặc định "
                             f"{SELF_IDLE_SECONDS})")
    parser.add_argument("--app", choices=TERM_APP_CHOICES,
                        default=TERM_APP_DEFAULT,
                        help=f"ứng dụng mở cửa sổ (mặc định "
                             f"{TERM_APP_DEFAULT})")
    return parser


def _short_error(text: str) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= SHORT_ERROR_MAX_CHARS:
        return compact
    return compact[:SHORT_ERROR_MAX_CHARS - 1] + "…"


def run_term_worker(opts) -> int:
    session_id = opts.session
    cwd = opts.cwd
    check_duration("--idle-sec", opts.idle_sec)
    log(f"bắt đầu: phiên {short_id(session_id)}, cwd {cwd}, app {opts.app}")
    if sys.platform != MACOS_PLATFORM:
        log(f"không phải macOS ({sys.platform}); bỏ cuộc")
        return EXIT_USAGE

    transcript = find_transcript(session_id)
    if transcript is None:
        log("không tìm thấy transcript; bỏ cuộc")
        return EXIT_NOT_FOUND
    log(f"chờ transcript {transcript.path} đứng yên {opts.idle_sec}s "
        f"(tối đa {SELF_MAX_WAIT_MINUTES} phút)")
    if not wait_for_idle(transcript.path, opts.idle_sec):
        log("transcript vẫn đang ghi; bỏ cuộc")
        return EXIT_NOT_FOUND
    log("transcript đã đứng yên")

    pids = tui_pids(session_id)
    if pids:
        pid_text = ", ".join(str(pid) for pid in pids)
        log(f"TUI của phiên vẫn còn sống (pid {pid_text}); không mở cửa sổ")
        return EXIT_CONFLICT
    if not Path(cwd).is_dir():
        log(f"không tìm thấy cwd {cwd}; bỏ cuộc")
        return EXIT_NOT_FOUND

    command = _shell_command(session_id, cwd)
    try:
        script = _write_command_file(session_id, command)
    except OSError as exc:
        log(f"không ghi được file .command: {exc}")
        return EXIT_CONFLICT
    log(f"mở cửa sổ {opts.app} cho phiên {short_id(session_id)} bằng {script}")
    try:
        result = subprocess.run(
            _open_argv(opts.app, script), capture_output=True, text=True,
            timeout=OPEN_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"không chạy được open: {exc}")
        return EXIT_CONFLICT
    if result.returncode != 0:
        detail = _short_error(result.stderr or result.stdout)
        log(f"open lỗi (mã {result.returncode}): {detail}")
        return EXIT_CONFLICT
    log(f"đã mở cửa sổ {opts.app} (mã {result.returncode})")
    return EXIT_OK
