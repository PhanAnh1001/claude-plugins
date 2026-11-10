"""hh-store CLI: `touch` (reader heartbeat + start indexer) and `status`."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

from . import paths, runtime

INDEXER_ENV = "HYBRID_HANDS_INDEXER"
OFF_VALUES = runtime.DISABLED_VALUES
ON_VALUES = frozenset({"1", "on", "true", "yes"})
INDEXER_BIN = Path(__file__).resolve().parents[2] / "bin" / "hh-indexer"


def _env(name: str) -> str:
    return os.environ.get(name, "").strip().lower()


def indexer_allowed() -> bool:
    return runtime.enabled() and _env(INDEXER_ENV) not in OFF_VALUES


def indexer_running(directory: Path) -> bool:
    """True when another process holds indexer.lock."""
    fd = os.open(directory / paths.INDEXER_LOCK_NAME, os.O_RDWR | os.O_CREAT, paths.FILE_MODE)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)  # closing drops our probe lock too
    return False


def _queue_dirty(directory: Path, targets: Iterable[str]) -> None:
    lines = "".join(f"{Path(t).expanduser().resolve()}\n" for t in targets)
    if not lines:
        return
    entry = paths.dirty_dir(directory) / f"{os.getpid()}-{time.monotonic_ns()}"
    tmp = entry.with_name("." + entry.name)  # dotfile then rename: indexer never reads half
    tmp.write_text(lines)
    os.replace(tmp, entry)


def _spawn(directory: Path) -> None:
    if indexer_running(directory):
        return
    subprocess.Popen([sys.executable, str(INDEXER_BIN)], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def touch(targets: Iterable[str] = ()) -> None:
    """Heartbeat + dirty queue + start the indexer if absent. Never raises."""
    if not indexer_allowed():
        return
    try:
        directory = paths.state_dir()
        paths.touch_last_read(directory)
        _queue_dirty(directory, targets)
        _spawn(directory)
    except Exception:  # noqa: BLE001 - contract: touch is best-effort and silent
        return


HOOK_STDIN_LIMIT = 1 << 20  # 1 MB: hook payloads are small; never slurp unbounded input
HOOK_PATH_KEYS = ("transcript_path", "agent_transcript_path")  # agent_*: SubagentStop


def hook_paths(raw: str) -> List[str]:
    """Existing absolute transcript paths from a Claude Code hook JSON payload."""
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    values = (data.get(key) for key in HOOK_PATH_KEYS)
    return [v for v in values if isinstance(v, str) and os.path.isabs(v) and os.path.exists(v)]


def _read_hook_stdin() -> str:
    try:
        return sys.stdin.read(HOOK_STDIN_LIMIT)
    except (OSError, ValueError, UnicodeDecodeError):
        return ""


def kick_from_reader() -> None:
    """hh-ps hook: like touch, but only for a terminal run unless forced on.

    Off under an isolated state dir and when stdout is not a tty (test harnesses,
    pipes); piped readers such as pane/Paseo call `hh-store touch` themselves.
    """
    forced = _env(INDEXER_ENV) in ON_VALUES
    if not forced and (os.environ.get(paths.STATE_DIR_ENV) or not sys.stdout.isatty()):
        return
    touch()


def status(directory: Path) -> dict:
    try:
        last_read: Optional[float] = (directory / paths.LAST_READ_NAME).stat().st_mtime
    except OSError:
        last_read = None
    return {"revision": paths.read_revision(directory),
            "indexer_running": indexer_running(directory), "last_read": last_read}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hh-store")
    sub = parser.add_subparsers(dest="command", required=True)
    touch_parser = sub.add_parser("touch")
    touch_parser.add_argument("--path", action="append", default=[])
    touch_parser.add_argument("--hook-stdin", action="store_true")
    sub.add_parser("status").add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 0
    if args.command == "touch":
        hooked = hook_paths(_read_hook_stdin()) if args.hook_stdin and indexer_allowed() else []
        touch([*args.path, *hooked])
        return 0
    info = status(paths.state_dir())
    print(json.dumps(info) if args.json else
          "\n".join(f"{key}: {value}" for key, value in info.items()))
    return 0
