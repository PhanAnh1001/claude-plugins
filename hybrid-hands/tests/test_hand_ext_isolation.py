"""hand-ext isolation: clean worktree, patch round-trip, conflict, cleanup, policy data rule."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

TESTS = Path(__file__).resolve().parent
HYBRID_HANDS = TESTS.parents[0]
PLUGIN = HYBRID_HANDS / "plugins" / "hybrid-hands"
FIXTURES = TESTS / "fixtures" / "hand_ext"
sys.path.insert(0, str(PLUGIN / "lib"))

from hand_ext import cli  # noqa: E402
from hand_ext.backends.base import Backend, Check, RunSpec, RunState, Status  # noqa: E402

FAKE_MODULE = "hand_ext.backends.isoft"
FAKE_HAND = FIXTURES / "isolation_fake.py"
SCENARIO_ENV = "ISO_SCENARIO"
PROBE_ENV = "ISO_PROBE"
CONFLICT_ENV = "ISO_CONFLICT_TARGET"
STATE_ENV = "HYBRID_HANDS_STATE_DIR"
TIMEOUT_S = 30
BRIEF = "MỤC TIÊU: kiểm tra cách ly\n"
CONFLICT_TRACKED = "user\n"
TRACKED_DIRTY = "dirty\n"
UNTRACKED_TEXT = "untracked\n"


class IsoBackend(Backend):
    """In-process backend that runs the fake hand in `spec.cwd`."""

    name = "isoft"

    def setup(self, options: dict) -> list:
        return []

    def doctor(self, options: dict) -> list:
        return [Check("stub", True, "ok")]

    def build_command(self, spec: RunSpec) -> tuple:
        target = os.environ.get(CONFLICT_ENV)
        if target:
            (Path(target) / "tracked.txt").write_text(CONFLICT_TRACKED, encoding="utf-8")
        mode = os.environ.get(SCENARIO_ENV, "ok")
        return [sys.executable, str(FAKE_HAND), mode], {}, None

    def parse_line(self, line: str, state: RunState) -> None:
        state.final_text += line + "\n"

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        return Status.OK if exit_code == 0 else Status.FAILED


def _register() -> None:
    module = types.ModuleType(FAKE_MODULE)
    module.IsoftBackend = IsoBackend
    sys.modules[FAKE_MODULE] = module


class IsolationCase(unittest.TestCase):
    def setUp(self) -> None:
        _register()
        self.tmp = Path(tempfile.mkdtemp(prefix="hand-ext-isolation-"))
        self.addCleanup(self._cleanup)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.worktrees = self.tmp / "worktrees"
        self.state = self.tmp / "state"
        self.probe = self.tmp / "probe.json"
        self.brief = self.tmp / "brief.md"
        self.brief.write_text(BRIEF, encoding="utf-8")
        self._write_repo()
        env = mock.patch.dict(os.environ, {STATE_ENV: str(self.state)})
        env.start()
        self.addCleanup(env.stop)

    def _cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        sys.modules.pop(FAKE_MODULE, None)

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True)

    def _config(self, root: Path, *, worktree_root: bool = True) -> None:
        section = {"order": ["isoft"], "backends": {"isoft": {}}}
        if worktree_root:
            section["worktree_root"] = str(self.worktrees)
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        (root / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"ext_hand": section}, ensure_ascii=False), encoding="utf-8")

    def _write_repo(self) -> None:
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        (self.repo / ".gitignore").write_text(
            ".env\n*.demo.env\nignored/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "gone.txt").write_text("gone\n", encoding="utf-8")
        self._config(self.repo)
        self._git("add", ".")
        self._git("commit", "-qm", "init")
        (self.repo / "tracked.txt").write_text(TRACKED_DIRTY, encoding="utf-8")
        (self.repo / "untracked.txt").write_text(UNTRACKED_TEXT, encoding="utf-8")
        (self.repo / ".env").write_text("DUMMY=1\n", encoding="utf-8")
        (self.repo / "notes.demo.env").write_text("DUMMY=2\n", encoding="utf-8")
        (self.repo / "ignored").mkdir()
        (self.repo / "ignored" / "secret.txt").write_text("secret\n", encoding="utf-8")
        old_report = self.repo / "output" / "llm" / "hand-ext" / "old"
        old_report.mkdir(parents=True)
        (old_report / "report.md").write_text("OLD REPORT\n", encoding="utf-8")

    def _cli(self, cwd: Path, *extra: str) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["run", "--brief", str(self.brief), "--backend", "isoft",
                             "--cwd", str(cwd), *extra])
        return code, out.getvalue(), err.getvalue()

    def _run(self, *extra: str) -> tuple:
        return self._cli(self.repo, *extra)

    def _latest(self, root: Path, name: str = "report.md") -> Path:
        paths = sorted((root / "output" / "llm" / "hand-ext").glob(f"*/{name}"),
                       key=lambda path: path.stat().st_mtime)
        self.assertTrue(paths, f"không thấy {name} dưới {root}")
        return paths[-1]

    def _scenario(self, mode: str = "ok", **extra: str) -> Any:
        values = {SCENARIO_ENV: mode, PROBE_ENV: str(self.probe)}
        values.update(extra)
        return mock.patch.dict(os.environ, values)


class WorktreeRoundTripTest(IsolationCase):
    def test_worktree_hides_ignored_and_applies_changes_back(self) -> None:
        with self._scenario():
            code, out, err = self._run("--keep-worktree")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("cách ly: worktree", out)
        self.assertIn("áp patch: ok (3 file)", out)
        seen = json.loads(self.probe.read_text(encoding="utf-8"))
        self.assertFalse(seen["env_exists"])
        self.assertFalse(seen["ignored_exists"])
        self.assertEqual(seen["tracked"], TRACKED_DIRTY)
        self.assertEqual(seen["untracked"], UNTRACKED_TEXT)
        self.assertNotEqual(Path(seen["cwd"]), self.repo)
        worktrees = [path for path in self.worktrees.iterdir() if path.is_dir()]
        self.assertEqual(len(worktrees), 1)
        worktree = worktrees[0]
        self.assertFalse((worktree / ".env").exists())
        self.assertFalse((worktree / "notes.demo.env").exists())
        self.assertFalse((worktree / "ignored").exists())
        self.assertFalse((worktree / "output").exists())
        self.assertTrue((worktree / "untracked.txt").is_file())
        report = self._latest(self.repo).read_text(encoding="utf-8")
        self.assertIn("Chế độ: `worktree`", report)
        self.assertIn("Áp về gốc: ok (3 file)", report)
        self.assertIn("giữ lại", report)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "hand\n")
        self.assertEqual((self.repo / "new.txt").read_text(encoding="utf-8"), "new\n")
        self.assertFalse((self.repo / "gone.txt").exists())
        self.assertIn("new.txt", self._latest(self.repo, "changes.patch").read_text(
            encoding="utf-8"))

    def test_untracked_secrets_and_outside_symlink_are_skipped(self) -> None:
        (self.repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        (self.repo / ".env.example").write_text("DUMMY=1\n", encoding="utf-8")
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "app.env").write_text("DUMMY=1\n", encoding="utf-8")
        outside = self.tmp / "outside.env"
        outside.write_text("DUMMY=1\n", encoding="utf-8")
        (self.repo / "link-out").symlink_to(outside)
        (self.repo / "inside.txt").write_text("x\n", encoding="utf-8")
        (self.repo / "link-abs").symlink_to(self.repo / "inside.txt")
        (self.repo / "link-rel").symlink_to("inside.txt")
        untracked = self._git("ls-files", "--others", "--exclude-standard").stdout.splitlines()
        self.assertIn(".env", untracked)
        with self._scenario():
            code, out, err = self._run("--keep-worktree")
        self.assertEqual(code, 0, (out, err))
        worktrees = [path for path in self.worktrees.iterdir() if path.is_dir()]
        self.assertEqual(len(worktrees), 1)
        worktree = worktrees[0]
        for rel in (".env", "sub/app.env", "link-out", "link-abs"):
            self.assertFalse((worktree / rel).exists(), rel)
            self.assertFalse((worktree / rel).is_symlink(), rel)
        self.assertFalse((worktree / "sub").exists())
        self.assertTrue((worktree / ".env.example").is_file())
        self.assertTrue((worktree / "link-rel").is_symlink())
        seen = json.loads(self.probe.read_text(encoding="utf-8"))
        self.assertFalse(seen["env_exists"])
        report = self._latest(self.repo).read_text(encoding="utf-8")
        self.assertIn("Bỏ qua file nghi bí mật", report)
        skip_line = next(line for line in report.splitlines()
                         if line.startswith("- Bỏ qua file nghi bí mật:"))
        skipped = skip_line.removeprefix("- Bỏ qua file nghi bí mật: ").split(", ")
        self.assertIn(".env", skipped)
        self.assertIn("sub/app.env", skipped)
        note = "symlink tuyệt đối hoặc ra ngoài repo hoặc tới file bí mật"
        self.assertIn(f"link-out ({note})", skipped)
        self.assertIn(f"link-abs ({note})", skipped)

    def test_conflict_keeps_user_changes_and_is_reported(self) -> None:
        with self._scenario(ISO_CONFLICT_TARGET=str(self.repo)):
            code, out, err = self._run()
        self.assertEqual(code, 0, (out, err))
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"),
                         CONFLICT_TRACKED)
        self.assertFalse((self.repo / "new.txt").exists())
        self.assertTrue((self.repo / "gone.txt").exists())
        report = self._latest(self.repo).read_text(encoding="utf-8")
        self.assertIn("xung đột", report)
        self.assertIn("không ghi đè", report)
        self.assertTrue((self._latest(self.repo, "changes.patch")).is_file())
        self.assertEqual(list(self.worktrees.iterdir()), [])

    def test_no_apply_keeps_workspace_and_saves_patch(self) -> None:
        with self._scenario():
            code, out, err = self._run("--no-apply")
        self.assertEqual(code, 0, (out, err))
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"),
                         TRACKED_DIRTY)
        self.assertFalse((self.repo / "new.txt").exists())
        self.assertTrue((self.repo / "gone.txt").exists())
        patch = self._latest(self.repo, "changes.patch").read_text(encoding="utf-8")
        self.assertIn("new.txt", patch)
        report = self._latest(self.repo).read_text(encoding="utf-8")
        self.assertIn("--no-apply", report)
        self.assertEqual(list(self.worktrees.iterdir()), [])

    def test_timeout_cleans_worktree_but_keeps_patch(self) -> None:
        with self._scenario("sleep"):
            code, out, _ = self._run("--timeout-min", "0.02")
        self.assertEqual(code, 6, out)
        self.assertIn("status: timeout", out)
        self.assertEqual(list(self.worktrees.iterdir()), [])
        patch = self._latest(self.repo, "changes.patch")
        self.assertTrue(patch.is_file())
        self.assertIn("Chế độ: `worktree`", self._latest(self.repo).read_text(
            encoding="utf-8"))

    def test_failed_run_cleans_worktree_but_keeps_patch(self) -> None:
        with self._scenario("fail"):
            code, out, _ = self._run()
        self.assertEqual(code, 1, out)
        self.assertIn("status: failed", out)
        self.assertEqual(list(self.worktrees.iterdir()), [])
        self.assertTrue(self._latest(self.repo, "changes.patch").is_file())


class IsolationFallbackTest(IsolationCase):
    def _plain(self) -> Path:
        plain = self.tmp / "plain"
        plain.mkdir()
        self._config(plain, worktree_root=False)
        return plain

    def test_non_git_cwd_falls_back_to_none_with_warning(self) -> None:
        plain = self._plain()
        with self._scenario():
            code, out, err = self._cli(plain)
        self.assertEqual(code, 0, (out, err))
        self.assertIn("không phải git repo", err)
        report = self._latest(plain).read_text(encoding="utf-8")
        self.assertIn("Chế độ: `none`", report)
        self.assertIn("không phải git repo", report)
        seen = json.loads(self.probe.read_text(encoding="utf-8"))
        self.assertEqual(Path(seen["cwd"]), plain.resolve())
        self.assertFalse((self.state / "worktrees").exists())

    def test_explicit_worktree_on_non_git_exits_2(self) -> None:
        plain = self._plain()
        code, _, err = self._cli(plain, "--isolation", "worktree")
        self.assertEqual(code, 2, err)
        self.assertIn("isolation=worktree", err)
        self.assertIn("không phải git repo", err)

    def test_explicit_none_runs_in_repo_cwd(self) -> None:
        with self._scenario():
            code, out, err = self._run("--isolation", "none")
        self.assertEqual(code, 0, (out, err))
        seen = json.loads(self.probe.read_text(encoding="utf-8"))
        self.assertEqual(Path(seen["cwd"]), self.repo.resolve())
        self.assertTrue(seen["env_exists"])
        self.assertIn("Chế độ: `none`", self._latest(self.repo).read_text(
            encoding="utf-8"))
        self.assertFalse((self.state / "worktrees").exists())

    def test_default_worktree_root_follows_state_dir(self) -> None:
        self._config(self.repo, worktree_root=False)
        with self._scenario():
            code, out, err = self._run("--keep-worktree")
        self.assertEqual(code, 0, (out, err))
        roots = [path for path in (self.state / "worktrees").iterdir() if path.is_dir()]
        self.assertEqual(len(roots), 1)
        self.assertEqual((roots[0] / "tracked.txt").read_text(encoding="utf-8"),
                         "hand\n")
        seen = json.loads(self.probe.read_text(encoding="utf-8"))
        self.assertEqual(Path(seen["cwd"]), roots[0].resolve())


class IsolationFailureTest(IsolationCase):
    def test_explicit_worktree_in_unborn_repo_exits_2_and_cleans(self) -> None:
        unborn = self.tmp / "unborn"
        unborn.mkdir()
        subprocess.run(["git", "-C", str(unborn), "init", "-q"], check=True)
        self._config(unborn)
        code, _, err = self._cli(unborn, "--isolation", "worktree")
        self.assertEqual(code, 2, err)
        self.assertIn("HEAD", err)
        self.assertEqual(list(self.worktrees.iterdir()), [])
        report = self._latest(unborn).read_text(encoding="utf-8")
        self.assertIn("Lỗi:", report)
        self.assertIn("HEAD", report)


class PolicyTextTest(unittest.TestCase):
    def test_data_rule_is_present_in_policy_surfaces(self) -> None:
        files = [
            PLUGIN / "scripts" / "session-start-policy.sh",
            PLUGIN / "scripts" / "inject-policy.sh",
            PLUGIN / "skills" / "ext-hand" / "SKILL.md",
            PLUGIN / "templates" / "ext-hand-preamble.md",
            HYBRID_HANDS / "README.md",
        ]
        for path in files:
            self.assertIn("dữ liệu khách hàng", path.read_text(encoding="utf-8"), str(path))
            self.assertIn("hand Claude", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
