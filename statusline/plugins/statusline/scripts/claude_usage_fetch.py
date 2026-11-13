#!/usr/bin/env python3
"""Fetch account v1 usage limits that the statusLine payload lacks (per-model weekly, extra usage).

Calls GET https://api.anthropic.com/api/oauth/usage (undocumented; the same data `/usage` writes to
~/.claude.json as cachedUsageUtilization) with the Claude Code OAuth access token. The token is read
inside this process only (macOS Keychain "Claude Code-credentials" via `security ... -w`, whose
argv carries no secret, else $CLAUDE_V1_HOME/.credentials.json), sent in a request header, and never
printed, logged or written. The cache keeps numbers only (no token, email or account id):
  $CLAUDE_V1_HOME/.statusline-claude-usage.json   mode 600, atomic rename
  {"version", "state": "ok"|"error", "error", "fetched_at", "last_ok_at", "failures",
   "next_try_at", "limits": [{"label", "kind", "percent", "resets_at", "active"}],
   "windows": {"seven_day"|"seven_day_opus"|...: {"utilization", "resets_at"}},
   "extra_usage": {...numbers...}}
An error (no token, 401, 429, network) keeps the last good limits and backs off exponentially.
statusline.sh starts this detached; running it by hand prints only percentages and resets.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CACHE_NAME = ".statusline-claude-usage.json"
LOCK_NAME = ".statusline-claude-usage.lock"
CACHE_VERSION = 1
REFRESH_SECONDS = 300          # user-chosen 5-minute cycle; the endpoint rate-limits hard
BACKOFF_MAX_SECONDS = 3600     # cap so a fixed problem recovers within an hour
LOCK_STALE_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 15
WINDOW_PREFIXES = ("five_hour", "seven_day")  # legacy per-window objects (seven_day_opus, ...)
EXTRA_FIELDS = ("is_enabled", "monthly_limit", "used_credits", "utilization", "currency",
                "spend_limit_reached")

Fetcher = Callable[[str], dict]


class FetchError(Exception):
    """Short, token-free reason (e.g. 'http 401', 'no token')."""


def v1_home() -> Path:
    return Path(os.environ.get("CLAUDE_V1_HOME", str(Path.home() / ".claude")))


def read_token(home: Path) -> str:
    raw = ""
    try:
        raw = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                             capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        raw = ""
    if not raw.strip():
        try:
            raw = (home / ".credentials.json").read_text(encoding="utf-8")
        except OSError:
            raw = ""
    try:
        token = json.loads(raw)["claudeAiOauth"]["accessToken"]
    except (ValueError, KeyError, TypeError):
        raise FetchError("no token") from None
    if not isinstance(token, str) or not token:
        raise FetchError("no token")
    return token


def http_fetch(token: str) -> dict:
    request = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}", "anthropic-beta": BETA_HEADER,
        "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise FetchError(f"http {error.code}") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise FetchError("network or bad json") from None


def epoch(text: object) -> Optional[int]:
    if not isinstance(text, str):
        return None
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def number(value: object) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def limit_label(item: dict) -> str:
    scope = item.get("scope") if isinstance(item.get("scope"), dict) else {}
    model = scope.get("model") if isinstance(scope.get("model"), dict) else {}
    name = model.get("display_name")
    return name if isinstance(name, str) and name else str(item.get("kind") or "")


def parse_usage(data: dict) -> dict:
    """Numbers only from the response: every limit entry plus extra usage."""
    root = data.get("utilization", data) if isinstance(data, dict) else {}
    limits = []
    for item in root.get("limits") or []:
        if isinstance(item, dict) and number(item.get("percent")) is not None:
            limits.append({"label": limit_label(item), "kind": str(item.get("kind") or ""),
                           "percent": item["percent"], "resets_at": epoch(item.get("resets_at")),
                           "active": bool(item.get("is_active"))})
    extra = root.get("extra_usage") if isinstance(root.get("extra_usage"), dict) else {}
    extra_usage = {k: extra[k] for k in EXTRA_FIELDS
                   if isinstance(extra.get(k), (bool, int, float, str))}
    windows = {key: {"utilization": value["utilization"], "resets_at": epoch(value.get("resets_at"))}
               for key, value in root.items() if key.startswith(WINDOW_PREFIXES)
               and isinstance(value, dict) and number(value.get("utilization")) is not None}
    return {"limits": limits, "windows": windows, "extra_usage": extra_usage}


def load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cache(path: Path, document: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=CACHE_NAME, dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def due(cache: dict, now: float) -> bool:
    last = number(cache.get("fetched_at")) or 0
    next_try = number(cache.get("next_try_at")) or 0
    return now - last >= REFRESH_SECONDS and now >= next_try


def refresh(home: Path, now: float, fetch: Fetcher = http_fetch,
            token_reader: Callable[[Path], str] = read_token, force: bool = False) -> dict:
    path = home / CACHE_NAME
    cache = load_cache(path)
    if not force and not due(cache, now):
        return cache
    try:
        document = {"version": CACHE_VERSION, "state": "ok", "fetched_at": int(now),
                    "last_ok_at": int(now), "failures": 0, "next_try_at": 0,
                    **parse_usage(fetch(token_reader(home)))}
    except FetchError as error:
        failures = int(number(cache.get("failures")) or 0) + 1
        backoff = min(REFRESH_SECONDS * 2 ** (failures - 1), BACKOFF_MAX_SECONDS)
        document = {**cache, "version": CACHE_VERSION, "state": "error", "error": str(error),
                    "fetched_at": int(now), "failures": failures, "next_try_at": int(now + backoff)}
        document.setdefault("limits", [])
    write_cache(path, document)
    return document


def with_lock(home: Path, action: Callable[[], dict]) -> Optional[dict]:
    lock = home / LOCK_NAME
    try:
        lock.mkdir()
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime < LOCK_STALE_SECONDS:
                return None
            lock.rmdir()
            lock.mkdir()
        except OSError:
            return None
    try:
        return action()
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def main(argv: list[str]) -> int:
    home = v1_home()
    if not home.is_dir():
        return 0
    force = "--force" in argv
    result = with_lock(home, lambda: refresh(home, time.time(), force=force))
    if "--print" in argv and result is not None:
        print(f"state={result.get('state')} error={result.get('error', '')}")
        for item in result.get("limits", []):
            print(f"{item['label']}: {item['percent']}% reset={item['resets_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
