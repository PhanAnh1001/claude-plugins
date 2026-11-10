"""Snapshot of a sparse worktree keeps skip-worktree paths (spike S0 case 3)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hand_ext import isolation  # noqa: E402

HIDDEN = "docs/hidden-data/item.txt"
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


class SparseSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = Path(tempfile.mkdtemp(prefix="hh-sparse-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        main, self.sparse = self.root / "main", self.root / "sparse"
        main.mkdir()
        git(main, "init", "-q", "-b", "main")
        for rel in ("src/app.txt", "src/gone.txt", HIDDEN):
            (main / rel).parent.mkdir(parents=True, exist_ok=True)
            (main / rel).write_text("base\n")
        git(main, "add", "-A")
        git(main, "commit", "-qm", "base")
        git(main, "worktree", "add", "-q", "--no-checkout", str(self.sparse), "-b", "sparse")
        git(self.sparse, "sparse-checkout", "set", "--no-cone", "/*", "!docs/hidden-data/")
        git(self.sparse, "checkout", "-q")
        self.assertFalse((self.sparse / HIDDEN).exists())

    def test_sparse_parent_baseline_and_final_patch_keep_excluded_paths(self) -> None:
        (self.sparse / "src/app.txt").write_text("dirty\n")
        (self.sparse / "src/gone.txt").unlink()
        cfg = SimpleNamespace(**{k: self.root / k for k in (
            "worktree_root", "runs_dir", "ledger", "quota_state", "machine_state_dir")})
        run_dir = self.root / "run"
        ctx = isolation.prepare(cfg, self.sparse, "t", run_dir, isolation.IsolationChoice("worktree"))
        git(ctx.worktree, "cat-file", "-e", f"{ctx.baseline_tree}:{HIDDEN}")
        self.assertEqual(ctx.dirty_files, ["src/app.txt", "src/gone.txt"])
        (ctx.worktree / "src/new.txt").write_text("new\n")
        isolation.finalize(ctx, run_dir, apply_changes=False)
        patch = (run_dir / isolation.CHANGES_PATCH_FILE).read_text()
        self.assertIn("src/new.txt", patch)
        self.assertNotIn(HIDDEN, patch)


if __name__ == "__main__":
    unittest.main()
