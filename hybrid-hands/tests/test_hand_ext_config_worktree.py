"""A linked git worktree without its own config reads the main repo's .claude/hybrid-hands.json."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext.config import load_config  # noqa: E402
from hand_ext.constants import CONFIG_SECTION, PROJECT_CONFIG_RELPATH  # noqa: E402

MAIN_CONFIG = {CONFIG_SECTION: {"order": ["codex"],
                                "backends": {"codex": {"effort": "low"}}}}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class WorktreeConfigFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.main = base / "main"
        self.main.mkdir()
        _git(self.main, "init", "-q")
        _git(self.main, "-c", "user.name=t", "-c", "user.email=t@t", "commit",
             "-q", "--allow-empty", "-m", "init")
        self.worktree = base / "wt"
        _git(self.main, "worktree", "add", "-q", str(self.worktree))

    def _write_config(self, root: Path, section: dict) -> None:
        path = root / PROJECT_CONFIG_RELPATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(section), encoding="utf-8")

    def test_worktree_reads_main_repo_config(self) -> None:
        self._write_config(self.main, MAIN_CONFIG)
        cfg = load_config(self.worktree)
        self.assertEqual(cfg.order, ["codex"])
        self.assertEqual(cfg.options("codex")["effort"], "low")

    def test_worktree_own_config_wins(self) -> None:
        self._write_config(self.main, MAIN_CONFIG)
        self._write_config(self.worktree, {CONFIG_SECTION: {"order": ["claude"]}})
        self.assertEqual(load_config(self.worktree).order, ["claude"])


if __name__ == "__main__":
    unittest.main()
