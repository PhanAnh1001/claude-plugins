#!/usr/bin/env python3
"""Fake `dsh` 0.2.1-rc.5 for hand-ext tests. Never prints secrets.

Like the real launcher it reads `<cwd>/.env` when present, so tests can prove the wrapper
starts it from a directory without one. Writes what it saw to $FAKE_DSH_PROBE (JSON):
cwd, whether a `.env` was loaded, names of *_API_KEY vars, whether the Go key matched
$FAKE_DSH_EXPECT_KEY, the HAND_EXT_DSH_* values and stdin. Scenario: $FAKE_DSH_SCENARIO
(success | quota | nokey), events from dsh_<scenario>.jsonl next to this file.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "0.2.1-rc.5"
CAPACITY_SCENARIOS = ("capacity_small", "capacity_large")
CAPACITY_EVENTS = "dsh_capacity.jsonl"
LARGE_PATCH_LINES = 30
SMALL_PATCH_LINES = 5
args = sys.argv[1:]
if args == ["--version"]:
    print(VERSION)
    sys.exit(0)
if "--dump-config" in args:
    print("- id: llm-pi-ai\n  config:\n    providers:\n      opencode-go: {}")
    sys.exit(0)
dotenv_loaded = Path(".env").is_file()
stdin = sys.stdin.read() if args[-1:] == ["-"] else ""
probe = {
    "cwd": os.getcwd(), "dotenv_loaded": dotenv_loaded, "argv": args, "stdin": stdin,
    "api_key_names": sorted(k for k in os.environ if k.endswith("_API_KEY")),
    "go_key_matches": os.environ.get("OPENCODE_GO_API_KEY") == os.environ.get(
        "FAKE_DSH_EXPECT_KEY"),
    "hand_env": {k: v for k, v in os.environ.items() if k.startswith("HAND_EXT_DSH_")},
    "dsh_env": {k: os.environ.get(k) for k in ("DSH_HOME", "DSH_PERMISSION_MODE",
                                               "DSH_TELEMETRY_MODE")},
}
Path(os.environ["FAKE_DSH_PROBE"]).write_text(json.dumps(probe), encoding="utf-8")
scenario = os.environ.get("FAKE_DSH_SCENARIO", "success")
if scenario in CAPACITY_SCENARIOS:
    counter = Path(os.environ["FAKE_DSH_COUNTER"])
    n = int(counter.read_text(encoding="utf-8") or 0) + 1 if counter.is_file() else 1
    counter.write_text(str(n), encoding="utf-8")
    workspace = Path(os.environ["HAND_EXT_DSH_WORKSPACE"])
    log = os.environ.get("FAKE_DSH_PROMPT_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as out:
            out.write(json.dumps({"n": n, "cwd": os.getcwd(),
                                  "workspace": str(workspace), "stdin": stdin}) + "\n")
    if scenario == "capacity_small":
        (workspace / "small.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    else:
        lines = LARGE_PATCH_LINES if n == 1 else SMALL_PATCH_LINES
        (workspace / "new.txt").write_text(
            "".join(f"line {index}\n" for index in range(lines)), encoding="utf-8")
        subprocess.run(["git", "add", "new.txt"], cwd=str(workspace), check=False,
                       capture_output=True)
    sys.stdout.write((HERE / CAPACITY_EVENTS).read_text(encoding="utf-8"))
    sys.stderr.write("dsh: run failed\n")
    sys.exit(1)
sys.stdout.write((HERE / f"dsh_{scenario}.jsonl").read_text(encoding="utf-8"))
if scenario != "success":
    sys.stderr.write("dsh: run failed\n")
sys.exit(0 if scenario == "success" else 1)
