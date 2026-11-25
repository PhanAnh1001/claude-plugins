"""Test open-gpt-brain bằng PATH giả: fake paseo và hand-ext ghi argv vào log, không gọi bản thật."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "bin" / "open-gpt-brain"
WORKSPACE_ID = "ws-1"
AGENT_ID = "agent-42"
ORIGINAL_CFG = {"profile": "hybrid", "other": {"keep": 1}}

FAKE_HAND_EXT = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write("hand-ext " + " ".join(args) + "\\n")
root = args[args.index("--cwd") + 1]
if args[:2] == ["profile", "set"]:
    path = os.path.join(root, ".claude", "hybrid-hands.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.load(open(path)) if os.path.exists(path) else {}
    data["profile"] = args[2]
    json.dump(data, open(path, "w"))
elif args[0] == "pick":
    print(json.dumps({"native": True}))
elif args[0] == "profile":
    print(json.dumps({"roles": {"brain": {"provider": "codex", "account": "v1",
                                          "model": "gpt-6.1-sol", "effort": "high"}}}))
"""

FAKE_PASEO = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write("paseo " + " ".join(args) + "\\n")
if args[:2] == ["agent", "inspect"]:
    print(json.dumps({"ParentAgentId": None}))
elif args[:2] == ["workspace", "ls"]:
    print(json.dumps([{"workspaceId": "%s", "name": "main", "cwd": os.environ["FAKE_ROOT"], "background": False}]))
elif args[0] == "run":
    if os.environ.get("FAKE_RUN_EXIT"):
        sys.exit(int(os.environ["FAKE_RUN_EXIT"]))
    print("%s")
""" % (WORKSPACE_ID, AGENT_ID)


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


@pytest.fixture
def env_setup(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".claude").mkdir()
    (root / ".claude" / "hybrid-hands.json").write_text(json.dumps(ORIGINAL_CFG))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_exec(bin_dir / "paseo", FAKE_PASEO)
    _write_exec(bin_dir / "hand-ext", FAKE_HAND_EXT)
    log = tmp_path / "calls.log"
    env = {k: v for k, v in os.environ.items() if k not in ("PASEO_AGENT_ID", "HAND_EXT")}
    env.update(PATH=f"{bin_dir}{os.pathsep}{env['PATH']}", FAKE_LOG=str(log),
               FAKE_ROOT=str(root.resolve()), HAND_EXT=str(bin_dir / "hand-ext"))
    return env, root, log


def _run(env: dict[str, str], root: Path, *args: str, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(script), "--cwd", str(root), *args], env=env, text=True, capture_output=True)


def _calls(log: Path, prefix: str) -> list[str]:
    return [line for line in log.read_text().splitlines() if line.startswith(prefix)] if log.exists() else []


def _cfg(root: Path) -> str:
    return (root / ".claude" / "hybrid-hands.json").read_text()


def test_gpt_brain_writes_profile_and_runs_paseo(env_setup) -> None:
    env, root, log = env_setup
    result = _run(env, root)
    assert result.returncode == 0, result.stderr
    cfg = json.loads(_cfg(root))
    assert cfg["profile"] == "gpt-mono"
    assert cfg["ext_hand"]["native"] == {"claude": "auto", "codex": "auto"}
    assert cfg["other"] == {"keep": 1}
    [run_call] = _calls(log, "paseo run")
    assert "--provider codex/gpt-6.1-sol --thinking high --mode full-access" in run_call
    assert f"--workspace {WORKSPACE_ID}" in run_call
    assert not _calls(log, "paseo agent detach")


def test_claude_v2_brain_uses_opus_bypass(env_setup) -> None:
    env, root, log = env_setup
    assert _run(env, root, "--brain", "claude-v2").returncode == 0
    [run_call] = _calls(log, "paseo run")
    assert "--provider claude-v2/claude-opus-5-5" in run_call
    assert "--mode bypassPermissions" in run_call


def test_rollback_when_paseo_run_fails(env_setup) -> None:
    env, root, _ = env_setup
    before = _cfg(root)
    result = _run({**env, "FAKE_RUN_EXIT": "1"}, root)
    assert result.returncode != 0
    assert _cfg(root) == before


def test_dry_run_changes_nothing(env_setup) -> None:
    env, root, log = env_setup
    before = _cfg(root)
    assert _run(env, root, "--dry-run").returncode == 0
    assert _cfg(root) == before
    assert not _calls(log, "paseo run")


def test_symlink_uses_hand_ext_next_to_real_script(env_setup, tmp_path: Path) -> None:
    env, root, log = env_setup
    plugin_bin = tmp_path / "plugin-bin"
    plugin_bin.mkdir()
    shutil.copy2(SCRIPT, plugin_bin / "open-gpt-brain")
    _write_exec(plugin_bin / "hand-ext", FAKE_HAND_EXT)
    link_dir = tmp_path / "links"
    link_dir.mkdir()
    (link_dir / "ogb").symlink_to(plugin_bin / "open-gpt-brain")
    del env["HAND_EXT"]
    (tmp_path / "bin" / "hand-ext").unlink()  # hand-ext trên PATH không được dùng
    result = _run(env, root, script=link_dir / "ogb")
    assert result.returncode == 0, result.stderr
    assert _calls(log, "hand-ext profile set gpt-mono")
