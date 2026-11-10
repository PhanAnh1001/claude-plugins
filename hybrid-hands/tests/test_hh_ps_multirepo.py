"""`hh-ps` loads side-session state from every repo a listed session lives in."""
from __future__ import annotations

__import__("os").environ["HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"] = "1"  # never read real account files
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
PLUGIN_LIB = TESTS.parent / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
sys.path.insert(0, str(TESTS / "fixtures" / "hh_ps"))

from fixture import HhFixture, NOW, dead_pid, iso  # noqa: E402
from hh_ps import cli, repos  # noqa: E402
from hh_store import runtime as store_runtime  # noqa: E402

OTHER_PARENT = "1da78d01-0000-4000-8000-000000000001"
OTHER_SIDE = "6da49dbb-0000-4000-8000-000000000002"
SIDE_NAME = "RV-12"
GIT_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def _git(*args: str) -> None:
    subprocess.run(["git", *GIT_IDENTITY, *args], check=True, capture_output=True)


class OtherRepoFixture(HhFixture):
    """Base tree plus repo B: a live parent session and its stopped worktree side."""

    def __init__(self) -> None:
        super().__init__()
        self.parent_sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"])
        self.repo_b = self.base / "repo-b"
        self.repo_b.mkdir()
        _git("-C", str(self.repo_b), "init", "-q")
        _git("-C", str(self.repo_b), "commit", "-q", "--allow-empty", "-m", "init")
        self.worktree = self.base / "repo-b-wt" / SIDE_NAME
        _git("-C", str(self.repo_b), "worktree", "add", "-q", str(self.worktree))
        self._session_file(self.parent_sleeper.pid, OTHER_PARENT, self.repo_b,
                           NOW - 3000, "parent-b", "busy", NOW - 60)
        self._session_file(dead_pid(1_300_001), OTHER_SIDE, self.worktree,
                           NOW - 2000, SIDE_NAME, "idle", NOW - 700)
        for session_id, cwd, mtime in ((OTHER_PARENT, self.repo_b, NOW - 60),
                                       (OTHER_SIDE, self.worktree, NOW - 700)):
            self._transcript(session_id, [json.dumps(
                {"type": "user", "cwd": str(cwd), "timestamp": iso(mtime)})], mtime)
        self._write_repo_b_state()

    def _write_repo_b_state(self) -> None:
        (self.repo_b / ".claude").mkdir()
        (self.repo_b / ".claude" / "hybrid-hands.json").write_text(json.dumps(
            {"side_session": {"state_dir": "sessions/side"}}), encoding="utf-8")
        state_dir = self.repo_b / "sessions" / "side"
        state_dir.mkdir(parents=True)
        (state_dir / f"{SIDE_NAME}.json").write_text(json.dumps({
            "name": SIDE_NAME, "uuid": OTHER_SIDE, "provider": "claude",
            "dir": str(self.worktree), "screen": "s", "watch_screen": "w",
            "max_tokens": 50000, "started": NOW - 2000, "status": "stopped",
            "handoff": "", "tokens_used": 0, "worktree": True,
            "parent_session": OTHER_PARENT,
        }), encoding="utf-8")

    def close(self) -> None:
        self.parent_sleeper.terminate()
        self.parent_sleeper.wait(timeout=10)
        super().close()


class HhPsMultiRepoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = OtherRepoFixture()
        self.addCleanup(self.fx.close)
        store_runtime._reset_for_tests()  # store follows each fixture HYBRID_HANDS_STATE_DIR
        self.addCleanup(store_runtime._reset_for_tests)

    def run_cli(self, *args: str) -> str:
        out = io.StringIO()
        with self.fx.env(), redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.fx.project)])
        self.assertEqual(code, 0, out.getvalue())
        return out.getvalue()

    def test_side_of_other_repo_nests_under_its_parent(self) -> None:
        sessions = {item["session_id"]: item
                    for item in json.loads(self.run_cli("--json"))["sessions"]}
        self.assertIn(OTHER_SIDE, sessions)
        self.assertEqual(sessions[OTHER_SIDE]["parent_session"], OTHER_PARENT)
        self.assertEqual(sessions[OTHER_SIDE]["side_name"], SIDE_NAME)

    def test_text_draws_other_repo_side_below_parent(self) -> None:
        lines = self.run_cli().splitlines()
        parent = next(i for i, line in enumerate(lines) if "parent-b" in line)
        side = next(i for i, line in enumerate(lines) if f"phụ:{SIDE_NAME}" in line)
        self.assertGreater(side, parent)
        self.assertTrue(lines[side].startswith(("│ ", "  ")), lines[side])

    def test_git_runs_once_per_session_directory(self) -> None:
        real = subprocess.run
        calls = []

        def counting(command, *args, **kwargs):
            if command and command[0] == "git":
                calls.append(tuple(command))
            return real(command, *args, **kwargs)

        with mock.patch.object(repos.subprocess, "run", side_effect=counting):
            self.run_cli("--json")
        self.assertEqual(len(calls), len(set(calls)), calls)
        self.assertLessEqual(len(calls), 6, calls)


if __name__ == "__main__":
    unittest.main()
