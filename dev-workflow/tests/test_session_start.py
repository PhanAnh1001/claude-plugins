"""Tests for scripts/session-start.sh (SessionStart hook)."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import PLUGIN_ROOT, SCRIPTS_DIR, SUBPROCESS_TIMEOUT_SECONDS, write_config

HOOK = SCRIPTS_DIR / "session-start.sh"


def run_hook(project_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
    return subprocess.run(
        ["bash", str(HOOK)], env=env, capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )


class SessionStartHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_silent_without_config(self) -> None:
        result = run_hook(self.project)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_suggests_skills_with_config(self) -> None:
        write_config(self.project, "")
        result = run_hook(self.project)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Start any task that changes code or docs with the skill dev-workflow:dev-triage.", result.stdout)
        for skill in ("jira-workflow", "trace-check"):
            self.assertIn(f"dev-workflow:{skill}", result.stdout)
        self.assertIn("dev-workflow:session-closeout", result.stdout)
        self.assertIn(f'"{PLUGIN_ROOT}/scripts/dw" config', result.stdout)
        self.assertIn(f'"{PLUGIN_ROOT}/scripts/dw" trace', result.stdout)

    def test_exits_0_when_project_dir_missing(self) -> None:
        result = run_hook(self.project / "does-not-exist")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_hook_is_executable(self) -> None:
        self.assertTrue(os.access(HOOK, os.X_OK))


if __name__ == "__main__":
    unittest.main()
