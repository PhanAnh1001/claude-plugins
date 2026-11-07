"""`side-session attach`: attach to a running side session's screen.

Pure helpers plus a menu loop; the caller injects screen ids/exec/input/output so tests
never run a real `screen`. No project config is needed: Paseo may start this from any cwd.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable

from . import constants as C
from . import screen

IdsFn = Callable[[], dict[str, str]]
ExecFn = Callable[[list[str]], int]
InputFn = Callable[[str], str]
PrintFn = Callable[[str], None]
TransportFn = Callable[[str], "tuple[str, str] | None"]

SCREEN_FALLBACKS = ("/usr/bin/screen", "/opt/homebrew/bin/screen", "/usr/local/bin/screen")
SCREEN_NOT_FOUND = ("side-session: không tìm thấy lệnh screen (đã tìm trong PATH, "
                    "/usr/bin/screen, /opt/homebrew/bin/screen, /usr/local/bin/screen)")
NO_SESSIONS = "Không có phiên phụ nào đang chạy."
REFRESH_PROMPT = "Enter để làm mới, q để thoát: "
MENU_PROMPT = "Chọn số (Enter làm mới, q thoát): "
MENU_ITEM = "{index}) {name}"
RUNNING_LABEL = "Đang chạy: {names}"
NAMED_NOT_FOUND = "side-session: không có phiên phụ đang chạy tên {name}"
INVALID_CHOICE = "Lựa chọn không hợp lệ: {answer}"
QUIT_ANSWER = "q"
EXIT_NOT_FOUND = 1
PASEO_HINT = ("side-session: phiên {name} do Paseo giữ (agent {agent}); "
              "mở app Paseo hoặc chạy: paseo attach {agent}")


def session_targets(ids: dict[str, str]) -> list[tuple[str, str]]:
    """(session name, `pid.name`) of side-session screens, not watchdogs, sorted by name."""
    targets = [
        (screen_name[len(C.SCREEN_PREFIX):], full_id)
        for screen_name, full_id in ids.items()
        if screen_name.startswith(C.SCREEN_PREFIX)
        and not screen_name.endswith(C.WATCH_SUFFIX)
    ]
    return sorted(targets)


def attach_argv(screen_bin: str, full_id: str) -> list[str]:
    """`screen -x pid.name`: shared attach, and unambiguous next to `side-x-watch`."""
    return [screen_bin, "-x", full_id]


def find_screen() -> str | None:
    """`screen` from PATH, else the usual absolute locations (Paseo's daemon PATH)."""
    found = shutil.which("screen")
    if found:
        return found
    for candidate in SCREEN_FALLBACKS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _ensure_screen_on_path(screen_bin: str) -> None:
    """`screen.screen_ids()` runs bare `screen`; make the located binary reachable."""
    folder = os.path.dirname(os.path.abspath(screen_bin))
    path = os.environ.get("PATH", "")
    if folder and folder not in path.split(os.pathsep):
        os.environ["PATH"] = f"{folder}{os.pathsep}{path}" if path else folder


def _print_running(targets: list[tuple[str, str]], print_fn: PrintFn) -> None:
    if not targets:
        print_fn(NO_SESSIONS)
        return
    print_fn(RUNNING_LABEL.format(names=", ".join(name for name, _ in targets)))


def paseo_hint(name: str, agent_id: str) -> str:
    return PASEO_HINT.format(name=name, agent=agent_id or "")


def _paseo_agent(name: str, transport_fn: TransportFn | None) -> str | None:
    if transport_fn is None:
        return None
    wanted = name[len(C.SCREEN_PREFIX):] if name.startswith(C.SCREEN_PREFIX) else name
    info = transport_fn(wanted)
    if info and info[0] == C.TRANSPORT_PASEO:
        return info[1]
    return None


def _attach_named(name: str, ids_fn: IdsFn, exec_fn: ExecFn, print_fn: PrintFn,
                  screen_bin: str) -> int:
    wanted = name[len(C.SCREEN_PREFIX):] if name.startswith(C.SCREEN_PREFIX) else name
    targets = session_targets(ids_fn())
    full_id = next((full for session, full in targets if session == wanted), None)
    if full_id is None:
        print_fn(NAMED_NOT_FOUND.format(name=wanted))
        _print_running(targets, print_fn)
        return EXIT_NOT_FOUND
    return exec_fn(attach_argv(screen_bin, full_id))


def _show_menu(targets: list[tuple[str, str]], print_fn: PrintFn) -> str:
    if not targets:
        print_fn(NO_SESSIONS)
        return REFRESH_PROMPT
    for index, (name, _) in enumerate(targets, start=1):
        print_fn(MENU_ITEM.format(index=index, name=name))
    return MENU_PROMPT


def _menu_loop(ids_fn: IdsFn, exec_fn: ExecFn, input_fn: InputFn, print_fn: PrintFn,
               screen_bin: str) -> int:
    while True:
        targets = session_targets(ids_fn())
        try:
            answer = input_fn(_show_menu(targets, print_fn)).strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if answer.lower() == QUIT_ANSWER:
            return 0
        if not answer:
            continue
        try:
            index = int(answer)
        except ValueError:
            print_fn(INVALID_CHOICE.format(answer=answer))
            continue
        if not 1 <= index <= len(targets):
            print_fn(INVALID_CHOICE.format(answer=answer))
            continue
        _, full_id = targets[index - 1]
        exec_fn(attach_argv(screen_bin, full_id))


def run_attach(name: str | None, *, ids_fn: IdsFn, exec_fn: ExecFn, input_fn: InputFn,
               print_fn: PrintFn, screen_bin: str,
               transport_fn: TransportFn | None = None) -> int:
    """Attach by name once, or show a menu until the user quits; returns an exit code."""
    if name is not None:
        agent_id = _paseo_agent(name, transport_fn)
        if agent_id is not None:
            wanted = name[len(C.SCREEN_PREFIX):] if name.startswith(C.SCREEN_PREFIX) else name
            print_fn(paseo_hint(wanted, agent_id))
            return 0
        return _attach_named(name, ids_fn, exec_fn, print_fn, screen_bin)
    return _menu_loop(ids_fn, exec_fn, input_fn, print_fn, screen_bin)


def main(name: str | None, transport_fn: TransportFn | None = None) -> int:
    if name is not None:
        agent_id = _paseo_agent(name, transport_fn)
        if agent_id is not None:
            wanted = name[len(C.SCREEN_PREFIX):] if name.startswith(C.SCREEN_PREFIX) else name
            print(paseo_hint(wanted, agent_id))
            return 0
    screen_bin = find_screen()
    if screen_bin is None:
        print(SCREEN_NOT_FOUND)
        return C.EXIT_USAGE
    _ensure_screen_on_path(screen_bin)
    return run_attach(name, ids_fn=screen.screen_ids, exec_fn=subprocess.call,
                      input_fn=input, print_fn=print, screen_bin=screen_bin,
                      transport_fn=transport_fn)
