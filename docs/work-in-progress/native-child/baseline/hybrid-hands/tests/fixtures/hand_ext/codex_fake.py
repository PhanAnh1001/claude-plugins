#!/usr/bin/env python3
"""Fake codex. FAKE_CODEX_SCENARIO: ok | weekly | quota | cap | hang | login."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

SCENARIO = os.environ.get("FAKE_CODEX_SCENARIO", "ok")
LOOP_MAX = 300  # bounded: the wrapper must kill us long before this
STEP = {"input_tokens": 1000, "cached_input_tokens": 200, "output_tokens": 100}
RESETS_AT = 4102444800  # 2100-01-01 UTC, epoch seconds


def token_line(n, used):
    total = {k: v * n for k, v in STEP.items()}
    limits = {"primary": {"used_percent": used, "window_minutes": 300,
                          "resets_at": RESETS_AT},
              "secondary": {"used_percent": 10, "window_minutes": 10080,
                            "resets_at": RESETS_AT + 1}, "plan_type": "plus"}
    if SCENARIO == "weekly":
        limits.update(primary={"used_percent": 3, "window_minutes": 10080,
                               "resets_at": RESETS_AT + 1}, secondary=None,
                      plan_type="prolite")
    return json.dumps({"type": "event_msg", "payload": {"type": "token_count",
        "info": {"total_token_usage": total},
        "rate_limits": limits}}) + "\n"


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        print("codex-cli 0.166.0")
        return 0
    prompt = sys.stdin.read()
    log = os.environ.get("FAKE_CODEX_LOG")
    if log:
        Path(log).write_text(json.dumps({
            "argv": argv, "prompt": prompt, "codex_home": os.environ.get("CODEX_HOME"),
            "env_keys": sorted(k for k in os.environ if "API_KEY" in k or k.startswith("OPENAI"))}))
    if SCENARIO == "login":
        print("Error: Not logged in. Run codex login", file=sys.stderr)
        return 1
    tid = str(uuid.uuid4())
    print(json.dumps({"type": "thread.started", "thread_id": tid}), flush=True)
    day = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "11" / "04"
    day.mkdir(parents=True, exist_ok=True)
    rollout = day / f"rollout-2026-11-04T00-00-00-{tid}.jsonl"
    if SCENARIO == "quota":
        rollout.write_text(token_line(1, 100))
        print(json.dumps({"type": "error", "message": "You've hit your usage limit."}), flush=True)
        return 1
    if SCENARIO in ("cap", "hang"):
        for n in range(1, LOOP_MAX):
            if SCENARIO == "cap":
                with open(rollout, "a") as fh:
                    fh.write(token_line(n, 5))
            time.sleep(0.2)
        return 0
    rollout.write_text(token_line(2, 42))
    Path(argv[argv.index("-o") + 1]).write_text("BÁO CÁO GIẢ\n1. **Kết quả**: xong\n")
    print(json.dumps({"type": "turn.completed", "usage": {}}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
