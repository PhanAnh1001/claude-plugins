"""Real OpenCode Go usage, read from the statusline plugin's cache.

The statusline plugin owns the only code allowed to read the OpenCode key: its
`scripts/go-usage-fetch.sh` calls the usage API and writes
`$CLAUDE_HOME/.statusline-go-usage.json`. hybrid-hands runs that script and reads the
cache; it never sees the key and never captures the script's output. The cache is shared
with the status line, so a run refreshes both at once.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from .constants import GO_FETCH_ENV, GO_LIVE_ENV

DEFAULT_CLAUDE_HOME = "~/.claude"
CACHE_NAME = ".statusline-go-usage.json"
INSTALLED_PLUGINS_RELPATH = Path("plugins") / "installed_plugins.json"
FETCH_SCRIPT_RELPATH = Path("scripts") / "go-usage-fetch.sh"
STATUSLINE_PLUGIN_KEY = "statusline@statusline-local"
STATUSLINE_PLUGIN_PREFIX = "statusline@"

STATE_OK = "ok"
STATE_ERROR = "error"
# (cache key, label shown in the line, strftime format of the reset time)
WINDOWS = (("rolling", "5h", "%H:%M"),
           ("weekly", "tuần", "%d/%m %H:%M"),
           ("monthly", "tháng", "%d/%m %H:%M"))
FRESH_SECONDS = 120
FETCH_TIMEOUT_S = 20
FETCH_WAIT_S = 10
FETCH_POLL_S = 0.5
MINUTES_PER_HOUR = 60
LIVE_LABEL = "hạn mức Go (thật): "
STALE_SUFFIX = " (cache {minutes} phút trước)"

Runner = Callable[..., Any]


def claude_home(env: Mapping[str, str]) -> Path:
    """`CLAUDE_HOME`, then `CLAUDE_CONFIG_DIR`, then `~/.claude`: what the script uses."""
    raw = env.get("CLAUDE_HOME") or env.get("CLAUDE_CONFIG_DIR") or DEFAULT_CLAUDE_HOME
    return Path(os.path.expanduser(str(raw)))


def cache_path(home: Path) -> Path:
    return home / CACHE_NAME


def find_fetch_script(env: Mapping[str, str], home: Path) -> Optional[Path]:
    """Explicit override, else the installed statusline plugin's fetch script."""
    override = str(env.get(GO_FETCH_ENV) or "").strip()
    if override:
        path = Path(os.path.expanduser(override))
        return path if path.is_file() else None
    return _installed_script(home)


def _installed_script(home: Path) -> Optional[Path]:
    manifest = home / INSTALLED_PLUGINS_RELPATH
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return None
    entries = plugins.get(STATUSLINE_PLUGIN_KEY)
    if entries is None:
        entries = next((value for key, value in plugins.items()
                        if str(key).startswith(STATUSLINE_PLUGIN_PREFIX)), None)
    install_path = _install_path(entries)
    if install_path is None:
        return None
    script = install_path / FETCH_SCRIPT_RELPATH
    return script if script.is_file() else None


def _install_path(entries: Any) -> Optional[Path]:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("installPath"), str):
            raw = entry["installPath"].strip()
            if raw:
                return Path(os.path.expanduser(raw))
    return None


def fetch(script: Path, home: Path, *, run_fn: Runner, now_fn: Callable[[], float],
          sleep_fn: Callable[[float], None], timeout_s: float = FETCH_TIMEOUT_S,
          wait_s: float = FETCH_WAIT_S) -> None:
    """Run the fetch script without capturing output; wait out another run's lock."""
    start = float(now_fn())
    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(home)
    try:
        run_fn(["bash", str(script)], env=env, stdin=subprocess.DEVNULL,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout_s)
    except Exception:  # noqa: BLE001 - the statusline fetch is best-effort, like the script
        return
    _wait_for_refresh(cache_path(home), start, now_fn, sleep_fn, wait_s)


def _wait_for_refresh(path: Path, start: float, now_fn: Callable[[], float],
                      sleep_fn: Callable[[float], None], wait_s: float) -> None:
    """A cache older than `start` means another fetch holds the lock: poll for its result."""
    if not _older_than(path, start):
        return
    deadline = start + float(wait_s)
    polls = int(math.ceil(float(wait_s) / FETCH_POLL_S))
    for _ in range(polls):
        if float(now_fn()) >= deadline:
            return
        sleep_fn(FETCH_POLL_S)
        if not _older_than(path, start):
            return


def _older_than(path: Path, start: float) -> bool:
    fetched = _fetched_at(path)
    return fetched is not None and fetched < start


def _fetched_at(path: Path) -> Optional[float]:
    data = _read_cache(path)
    return _number((data or {}).get("fetched_at"))


def _read_cache(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def read_live(path: Path, now: float) -> Optional[Dict[str, Any]]:
    """Fresh `ok` cache, or an `error` cache that kept the last good windows; else None."""
    data = _read_cache(path)
    if data is None:
        return None
    windows = _windows(data.get("windows"))
    if windows is None:
        return None
    state = data.get("state")
    if state == STATE_OK:
        fetched = _number(data.get("fetched_at"))
        if fetched is None:
            return None
        age_s = max(0, int(float(now) - fetched))
        return {"fresh": age_s < FRESH_SECONDS, "age_s": age_s, "windows": windows}
    if state == STATE_ERROR:
        last_ok = _number(data.get("last_ok_at"))
        if last_ok is None:
            return None
        age_s = max(0, int(float(now) - last_ok))
        return {"fresh": False, "age_s": age_s, "windows": windows}
    return None


def _windows(raw: Any) -> Optional[Dict[str, Dict[str, float]]]:
    if not isinstance(raw, dict):
        return None
    windows: Dict[str, Dict[str, float]] = {}
    for cache_key, label, _ in WINDOWS:
        window = raw.get(cache_key)
        if not isinstance(window, dict):
            return None
        percent = _number(window.get("percent"))
        resets_at = _number(window.get("resets_at"))
        if percent is None or resets_at is None:
            return None
        windows[label] = {"percent": percent, "resets_at": resets_at}
    return windows


def live_line(live: Dict[str, Any], now: float) -> str:
    """One line with the real percentages and local reset times; `~` when cached."""
    fresh = bool(live.get("fresh"))
    mark = "" if fresh else "~"
    parts = []
    for _, label, fmt in WINDOWS:
        window = live["windows"][label]
        reset = time.strftime(fmt, time.localtime(float(window["resets_at"])))
        parts.append(f"{mark}{float(window['percent']):.0f}% {label} (reset {reset})")
    line = LIVE_LABEL + ", ".join(parts)
    if not fresh:
        minutes = max(1, int(live.get("age_s") or 0) // MINUTES_PER_HOUR)
        line += STALE_SUFFIX.format(minutes=minutes)
    return line


def refresh_and_read(cfg_live: bool, env: Mapping[str, str], *,
                     run_fn: Runner = subprocess.run, now_fn: Callable[[], float] = time.time,
                     sleep_fn: Callable[[float], None] = time.sleep) -> Optional[Dict[str, Any]]:
    """Refresh (when enabled and installed) then read the cache; never raise."""
    try:
        if not cfg_live or env.get(GO_LIVE_ENV) == "0":
            return None
        home = claude_home(env)
        script = find_fetch_script(env, home)
        if script is not None:
            fetch(script, home, run_fn=run_fn, now_fn=now_fn, sleep_fn=sleep_fn)
        return read_live(cache_path(home), now_fn())
    except Exception:  # noqa: BLE001 - live usage must never break a run or a command
        return None
