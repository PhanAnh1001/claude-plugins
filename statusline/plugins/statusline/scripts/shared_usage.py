"""Bounded read-only access to shared validated quota sources; never reads credentials."""
from __future__ import annotations

import importlib
import math
import signal
import sys
import time
from contextlib import contextmanager

from shared_prices import plugin_candidates


@contextmanager
def bounded():
    def expired(_signum, _frame):
        raise TimeoutError("local usage deadline")
    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0.75)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)


def shared_module(name):
    for plugin in plugin_candidates():
        lib = plugin / "lib"
        if (lib / "hh_ps" / "codex.py").is_file():
            sys.path.insert(0, str(lib))
            return importlib.import_module("hh_ps." + name)
    raise ImportError("shared usage unavailable")


def percent(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and 0 <= value <= 100:
            return float(value)
    return None


def account_windows(now):
    try:
        with bounded():
            account = shared_module("codex").load_codex(None, now).account
            result = {}
            for label in ("5h", "tuần"):
                sample = account.get(label)
                if sample is not None and sample.source == "codex_rollout" and 0 <= now - sample.at < 86400 and sample.usable(now):
                    value = percent(sample.pct)
                    if value is not None:
                        result[label] = (value, sample.at)
            return result
    except Exception:
        return {}


def claude_five(now):
    try:
        with bounded():
            return percent(shared_module("usage_enrichment")._five_hour("Claude", now))
    except Exception:
        return None


if __name__ == "__main__":
    value = claude_five(time.time()) if sys.argv[1:] == ["claude"] else None
    if value is not None:
        print(value)
