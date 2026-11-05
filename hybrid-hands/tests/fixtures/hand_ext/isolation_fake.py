#!/usr/bin/env python3
"""Fake hand for isolation tests: writes a probe, edits the workspace, optionally sleeps."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

SLEEP_SECONDS = 60
FAIL_CODE = 3
REPORT = "BÁO CÁO GIẢ\n1. **Kết quả**: xong\n"


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
    cwd = Path.cwd()
    probe = Path(os.environ["ISO_PROBE"])
    untracked = cwd / "untracked.txt"
    probe.write_text(json.dumps({
        "cwd": str(cwd),
        "env_exists": (cwd / ".env").exists(),
        "ignored_exists": (cwd / "ignored" / "secret.txt").exists(),
        "tracked": (cwd / "tracked.txt").read_text(encoding="utf-8")
        if (cwd / "tracked.txt").is_file() else None,
        "untracked": untracked.read_text(encoding="utf-8") if untracked.is_file() else None,
    }), encoding="utf-8")
    if (cwd / "tracked.txt").is_file():
        (cwd / "tracked.txt").write_text("hand\n", encoding="utf-8")
    (cwd / "new.txt").write_text("new\n", encoding="utf-8")
    if (cwd / "gone.txt").exists():
        (cwd / "gone.txt").unlink()
    print(REPORT, end="", flush=True)
    if mode == "sleep":
        time.sleep(SLEEP_SECONDS)
        return 0
    return FAIL_CODE if mode == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
