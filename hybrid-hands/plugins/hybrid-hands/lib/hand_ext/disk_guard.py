"""Shared disk preflight; no directories are created by this helper."""
from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

GIB = 1024 ** 3
EXIT_DISK_GUARD = 9
DEFAULT_WARN_GB = 20
DEFAULT_BLOCK_GB = 5


class DiskGuardBlocked(OSError):
    """Insufficient space to create an isolated checkout."""


def check_disk(root: Path, config: dict | None = None, *, ignore: bool = False) -> float:
    """Return free GiB; warn below warn_gb, raise below block_gb unless overridden."""
    if config is not None and not isinstance(config, dict):
        raise ValueError("disk_guard must be an object or null")
    options = config if config is not None else {}
    warn = options.get("warn_gb", DEFAULT_WARN_GB)
    block = options.get("block_gb", DEFAULT_BLOCK_GB)
    try:
        valid = (type(warn) in (int, float) and type(block) in (int, float)
                 and math.isfinite(warn) and math.isfinite(block)
                 and 0 <= block <= warn)
    except (OverflowError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("disk_guard requires finite numeric 0 <= block_gb <= warn_gb")
    ancestor = Path(root).resolve()
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free / GIB
    message = f"disk_guard: {free:.1f} GiB free; run side-session gc (dry-run)"
    if free < block and not ignore:
        raise DiskGuardBlocked(message + "; use --ignore-disk-guard to override")
    if free < warn:
        print("warning: " + message, file=sys.stderr)
    return free
