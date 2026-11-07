"""Ghi mục trust cho workdir vào `<codex_home>/config.toml` trước khi mở phiên Codex.

Codex TUI hỏi "Trust this folder?" với thư mục chưa được tin; phiên chạy không người trực
sẽ kẹt ở câu hỏi đó. Chỉ nối thêm bảng `[projects."<workdir>"]` khi config chưa có bảng
ấy, không định dạng lại phần còn lại của file.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import constants as C

try:
    import tomllib
except ImportError:  # Python 3.10 trở xuống không có tomllib
    tomllib = None

CONFIG_FILE = "config.toml"
PROJECTS_KEY = "projects"
TRUST_KEY = "trust_level"
TRUST_LEVEL = "trusted"
# Prelude chạy trong screen ngay trước `exec codex`, nên chỉ ghi khi thật sự mở phiên.
PRELUDE_CODE = (
    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
    "from side_session.codex_trust import ensure_codex_trust; "
    "ensure_codex_trust(Path(sys.argv[2]), sys.argv[3])"
)


def _table_header(workdir: str) -> str:
    return f"[{PROJECTS_KEY}.{json.dumps(workdir)}]"


def _matches_header(line: str, header: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(header):
        return False
    rest = stripped[len(header):].strip()
    return not rest or rest.startswith("#")


def _has_project_table(text: str, workdir: str) -> bool:
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            pass  # config hỏng: vẫn dò header bằng chuỗi để không thêm trùng
        else:
            projects = data.get(PROJECTS_KEY)
            return isinstance(projects, dict) and workdir in projects
    header = _table_header(workdir)
    return any(_matches_header(line, header) for line in text.splitlines())


def ensure_codex_trust(codex_home: Path, workdir: str) -> bool:
    """Thêm trust cho `workdir` nếu chưa có; trả về True khi config.toml vừa được ghi."""
    path = codex_home / CONFIG_FILE
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if _has_project_table(old, workdir):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if old and not old.endswith("\n"):
            fh.write("\n")
        fh.write(f'{_table_header(workdir)}\n{TRUST_KEY} = "{TRUST_LEVEL}"\n')
    return True


def prelude_argv(codex_home: Path, workdir: str) -> list[str]:
    """argv của prelude: nạp module này từ lib của plugin rồi ghi trust."""
    lib = Path(__file__).resolve().parents[1]
    return [sys.executable, "-c", PRELUDE_CODE, str(lib), str(codex_home), workdir]


class ConfigWriteError(RuntimeError):
    """Native config write failed; the message never contains stdout/stderr/config."""


_EOF = object()


def _pump(stream, messages: "queue.Queue[object]") -> None:
    """Forward complete JSON-RPC lines; drop non-JSON noise without logging it."""
    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                messages.put(message)
    finally:
        messages.put(_EOF)


def _send(proc, message: dict) -> None:
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _await_id(messages: "queue.Queue[object]", expected_id: int, deadline: float) -> dict:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ConfigWriteError("CONFIG_WRITE_TIMEOUT")
        try:
            message = messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise ConfigWriteError("CONFIG_WRITE_TIMEOUT") from exc
        if message is _EOF:
            raise ConfigWriteError("CONFIG_WRITE_EOF")
        if not isinstance(message, dict) or message.get("id") != expected_id:
            continue
        if message.get("error"):
            raise ConfigWriteError("CONFIG_WRITE_REJECTED")
        return message


def _stop_app_server(proc) -> bool:
    """Close stdin, wait for exit, then terminate/kill only this child.

    Returns True when the child had to be signalled (its exit code is then not a
    meaningful config-write status).
    """
    try:
        proc.stdin.close()
    except (OSError, ValueError):
        pass
    try:
        try:
            proc.wait(timeout=C.CODEX_CONFIG_RPC_EXIT_S)
            return False
        except subprocess.TimeoutExpired:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=C.CODEX_CONFIG_RPC_KILL_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=C.CODEX_CONFIG_RPC_KILL_S)
        return True
    finally:
        proc.stdout.close()


def ensure_codex_compact_limit(codex_home: Path, limit: int) -> bool:
    """Write the compact key through the native `codex app-server` config RPC.

    The Paseo 0.15.0 providerOptions schema rejects this Codex key, and Python 3.9
    here has no TOML writer. The app-server owns TOML formatting (comments/multiline
    preserved); it runs only for this one config write, without a thread/turn/model
    list/auth read. Config and credential contents are never read or printed here.
    """
    codex_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["CODEX_HOME"] = str(codex_home)
    try:
        proc = subprocess.Popen(
            [C.CODEX_APP_SERVER, "app-server"],
            cwd=str(codex_home), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    except OSError as exc:
        raise ConfigWriteError("CONFIG_WRITE_SPAWN_FAILED") from exc
    messages: "queue.Queue[object]" = queue.Queue()
    pump = threading.Thread(target=_pump, args=(proc.stdout, messages), daemon=True)
    pump.start()
    deadline = time.monotonic() + C.CODEX_CONFIG_RPC_TIMEOUT_S
    failure = None
    forced = False
    try:
        _send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": C.CODEX_CONFIG_CLIENT_NAME,
                                      "version": C.CODEX_CONFIG_CLIENT_VERSION}}})
        _await_id(messages, 1, deadline)
        _send(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
        _send(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "config/value/write",
            "params": {"keyPath": C.CODEX_COMPACT_KEY, "value": limit,
                       "mergeStrategy": "replace"}})
        _await_id(messages, 2, deadline)
    except ConfigWriteError as exc:
        failure = exc
    except (OSError, ValueError) as exc:
        failure = ConfigWriteError("CONFIG_WRITE_IO")
        failure.__cause__ = exc
    finally:
        try:
            forced = _stop_app_server(proc)
        finally:
            pump.join(timeout=C.CODEX_CONFIG_RPC_KILL_S)
    if failure is not None:
        raise failure
    if proc.returncode != 0 and not forced:
        raise ConfigWriteError("CONFIG_WRITE_EXIT")
    return True
