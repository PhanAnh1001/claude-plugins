#!/usr/bin/env python3
"""Fake backend that deletes its run dir mid-run, then keeps reporting tokens/final text.

Usage: rundir_fake.py <run_dir> delete|keep
"""
import json
import shutil
import sys
from pathlib import Path

RUN_DIR = Path(sys.argv[1])
MODE = sys.argv[2]
TOKEN_EVENT = {"input": 1234, "cached_input": 56, "output": 78}
FINAL_TEXT = "BÁO CÁO GIẢ\n1. **Kết quả**: xong\n"
STDERR_LINE = "fake backend: dọn file tạm trình duyệt"


def main() -> int:
    sys.stdin.read()
    if MODE == "delete":
        shutil.rmtree(RUN_DIR)
    print(STDERR_LINE, file=sys.stderr, flush=True)
    print(json.dumps(TOKEN_EVENT), flush=True)
    print(json.dumps({"final": FINAL_TEXT}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
