"""SessionStart hint: suggest worktree GC when the repo's disk runs low.

Cheap by design: one shutil.disk_usage call and one short git command.
Never runs gc and never raises; any failure yields an empty string.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hand_ext.disk_guard import DEFAULT_WARN_GB, GIB

# Short enough that a hung git never delays session start noticeably.
GIT_TIMEOUT_SECONDS = 2
WORKTREE_LINE_PREFIX = "worktree "


def extra_worktree_count(cwd: Path) -> int:
    result = subprocess.run(["git", "-C", str(cwd), "worktree", "list", "--porcelain"],
                            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=True)
    total = sum(line.startswith(WORKTREE_LINE_PREFIX) for line in result.stdout.splitlines())
    return max(total - 1, 0)


def disk_reminder(cwd: Path) -> str:
    """Return one reminder line, or "" when space is fine or anything fails."""
    try:
        free = shutil.disk_usage(cwd).free / GIB
        if free >= DEFAULT_WARN_GB:
            return ""
        extra = extra_worktree_count(cwd)
    except Exception:
        return ""
    if extra < 1:
        return ""
    return (f"NHẮC DỌN WORKTREE: ổ đĩa còn {free:.1f} GiB trống (< {DEFAULT_WARN_GB} GiB), "
            f"repo có {extra} worktree phụ; chạy `side-session gc` (xem trước) rồi `side-session gc --apply`.")
