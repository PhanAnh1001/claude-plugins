#!/usr/bin/env python3
"""Fake `codex` for hand-gpt tests. Scenario via FAKE_CODEX_SCENARIO: ok | cap | flex."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

SCENARIO = os.environ.get("FAKE_CODEX_SCENARIO", "ok")
VERSION = os.environ.get("FAKE_CODEX_VERSION", "0.156.0")
CAP_LOOP_MAX = 300  # bounded: the wrapper must kill us long before this
USAGE_STEP = {"input_tokens": 100000, "cached_input_tokens": 20000, "output_tokens": 10000}


def emit(event):
    print(json.dumps(event), flush=True)


def token_event(total, last):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": total, "last_token_usage": last}}}


def scaled(n):
    return {k: v * n for k, v in USAGE_STEP.items()}


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        print(f"codex-cli {VERSION}")
        return 0
    out = Path(argv[argv.index("-o") + 1])
    prompt = sys.stdin.read()
    log = os.environ.get("FAKE_CODEX_ARGV_LOG")
    if log:
        Path(log).write_text(json.dumps({"argv": argv, "prompt": prompt,
                                         "codex_home": os.environ.get("CODEX_HOME")}))
    tid = str(uuid.uuid4())
    rollout = Path(os.environ["CODEX_HOME"]) / "sessions/2026/11/04" / f"rollout-2026-11-04T00-00-00-{tid}.jsonl"
    rollout.parent.mkdir(parents=True, exist_ok=True)
    emit({"type": "thread.started", "thread_id": tid})
    emit({"type": "turn.started"})
    if SCENARIO == "flex":
        emit({"type": "error", "message": "429 Too Many Requests: flex tier resource unavailable"})
        emit({"type": "turn.failed", "error": {"message": "flex capacity"}})
        return 1
    with open(rollout, "a") as roll:
        steps = CAP_LOOP_MAX if SCENARIO == "cap" else 2
        for n in range(1, steps + 1):
            roll.write(json.dumps(token_event(scaled(n), USAGE_STEP)) + "\n")
            roll.flush()
            if SCENARIO == "cap":
                time.sleep(0.2)
    out.write_text("1. **Kết quả**: xong\n2. ok\n")
    emit({"type": "turn.completed", "usage": scaled(2)})
    return 0


sys.exit(main())
