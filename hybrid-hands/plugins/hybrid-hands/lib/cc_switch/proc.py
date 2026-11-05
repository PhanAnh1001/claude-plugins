"""Process-table helpers for `paseo --self` (no shell, bounded `ps` calls)."""
from __future__ import annotations

import os
import subprocess
from typing import List, Optional

from hh_ps.claude_source import pid_alive

from .constants import MAX_ANCESTRY_DEPTH, PS_TIMEOUT_SECONDS, ZOMBIE_STATE_PREFIX

_PS_AVAILABLE: Optional[bool] = None


def _ps_value(option: str, pid: int) -> Optional[str]:
    """One `ps -o <option>` field, or None when `ps` cannot answer."""
    global _PS_AVAILABLE
    if _PS_AVAILABLE is False:
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", option, "-p", str(pid)],
            capture_output=True, text=True, timeout=PS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        _PS_AVAILABLE = False
        return None
    _PS_AVAILABLE = True
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return text or None


def process_alive(pid: int) -> bool:
    """Like `pid_alive`; a zombie counts as exited when `ps` can report it."""
    if not pid_alive(pid):
        return False
    state = _ps_value("stat=", pid)
    if state is None:
        return True
    return not state.startswith(ZOMBIE_STATE_PREFIX)


def parent_pid(pid: int) -> Optional[int]:
    text = _ps_value("ppid=", pid)
    if text is None:
        return None
    try:
        return int(text.split()[0])
    except (IndexError, ValueError):
        return None


def ancestors(pid: int) -> Optional[List[int]]:
    """Parent chain of `pid`; None if a step cannot be resolved."""
    chain: List[int] = []
    seen = set()
    current = pid
    for _ in range(MAX_ANCESTRY_DEPTH):
        if current <= 0 or current in seen:
            break
        seen.add(current)
        parent = parent_pid(current)
        if parent is None:
            return None
        if parent <= 0 or parent == current:
            break
        chain.append(parent)
        current = parent
    return chain


def select_tui_pid(pids: List[int],
                   current_pid: Optional[int] = None) -> Optional[int]:
    """The TUI pid, using ancestry only when more than one candidate is live."""
    unique = sorted({int(pid) for pid in pids})
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    chain = ancestors(current_pid if current_pid is not None else os.getpid())
    if chain is None:
        return None
    matches = [pid for pid in unique if pid in chain]
    return matches[0] if len(matches) == 1 else None
