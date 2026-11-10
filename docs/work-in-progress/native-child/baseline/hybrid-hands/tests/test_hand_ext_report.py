"""hand-ext report: one repo, including the ledgers of its linked worktrees."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext import cli  # noqa: E402

TOKENS = {"input": 10, "cached_input": 2, "output": 3}
LEDGER = "state/hand_usage.json"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def entry(run_id: str, cwd: Path, label: str, tokens: int = 10) -> dict:
    return {"run_id": run_id, "started": "2026-11-07T10:00:00+07:00",
            "backend": "dsh", "label": label, "cwd": str(cwd),
            "tokens": {**TOKENS, "input": tokens}}


def write_ledger(root: Path, entries: list[dict]) -> None:
    path = root / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries), encoding="utf-8")


class WorktreeReportTest(unittest.TestCase):
    def test_report_counts_linked_worktree_ledger_once(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            repo, worktree, other = tmp / "repo", tmp / "wt", tmp / "other"
            for path in (repo, other):
                path.mkdir()
                git(path, "init", "-q")
                git(path, "-c", "user.name=t", "-c", "user.email=t@e",
                    "commit", "--allow-empty", "-qm", "init")
            git(repo, "worktree", "add", "-q", str(worktree))
            for root in (repo, worktree, other):
                (root / ".claude").mkdir()
                (root / ".claude" / "hybrid-hands.json").write_text(
                    json.dumps({"ext_hand": {"ledger": LEDGER,
                                             "worktree_root": str(tmp / "leftovers")}}),
                    encoding="utf-8")
                write_ledger(root, [])
            write_ledger(repo, [entry("main", repo, "main-run", 10),
                                entry("shared", repo, "chosen-copy", 20)])
            write_ledger(worktree, [entry("wt", worktree, "worktree-run", 30),
                                    entry("shared", worktree, "other-copy", 40)])
            write_ledger(other, [entry("other", other, "other-repo", 50)])
            # Deleted worktree: no .git left, so only metadata can identify the repo.
            # `base`-style SHA values are never treated as a repo path.
            left = tmp / "leftovers" / "gone"
            (left / ".claude").mkdir(parents=True)
            (left / ".claude" / "hybrid-hands.json").write_text(
                json.dumps({"ext_hand": {"ledger": LEDGER}}), encoding="utf-8")
            legacy = entry("gone", tmp / "removed", "gone-run", 60)
            legacy["git_common_dir"] = str((repo / ".git").resolve())
            meta_run = entry("meta-run", tmp / "removed", "meta-run", 80)
            sha_only = entry("sha-only", tmp / "removed", "sha-only", 70)
            sha_only["git_common_dir"] = "a" * 40
            write_ledger(left, [legacy, meta_run, sha_only])
            # The run's own meta.json is the other place a deleted cwd can leave evidence.
            run_dir = repo / "output" / "llm" / "hand-ext" / "meta-run"
            run_dir.mkdir(parents=True)
            (run_dir / "meta.json").write_text(json.dumps(
                {"git_common_dir": str((repo / ".git").resolve())}), encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(["report", "--cwd", str(repo)])
            text = out.getvalue()
            self.assertEqual(code, 0, text)
            self.assertIn("Tổng lượt: 5", text)
            self.assertIn("worktree-run", text)
            self.assertIn("gone-run", text)
            self.assertIn("meta-run", text)
            self.assertIn("chosen-copy", text)
            self.assertNotIn("other-copy", text)
            self.assertNotIn("other-repo", text)
            self.assertNotIn("sha-only", text)
            self.assertIn(str(worktree.resolve()), text)
            # No --cwd means the repo of the current directory, same scope.
            cwd = os.getcwd()
            os.chdir(repo)
            try:
                default_out = io.StringIO()
                with redirect_stdout(default_out):
                    self.assertEqual(cli.main(["report"]), 0)
            finally:
                os.chdir(cwd)
            self.assertIn("Tổng lượt: 5", default_out.getvalue())
            # A report reads ledgers; it must not leave lock files in either repo.
            self.assertEqual(list(repo.rglob("*.lock")), [])
            self.assertEqual(list(worktree.rglob("*.lock")), [])


if __name__ == "__main__":
    unittest.main()
