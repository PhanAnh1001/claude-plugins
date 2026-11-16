"""hand-ext run --role: backend/model/effort from the profile cell, role trail in meta."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hand_ext import run_cmd  # noqa: E402
from hand_ext.backends import get_backend  # noqa: E402
from hand_ext.cli import main  # noqa: E402

CTX = SimpleNamespace(base_commit="abc", dirty=False, worktree=None, dirty_files=[], run_cwd=Path("."))


class RunRoleTest(unittest.TestCase):
    def run_cli(self, argv):
        """Run `hand-ext run` up to the shell runner; return (code, cfg, args, meta)."""
        captured = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude/hybrid-hands.json").write_text(json.dumps({
                "profile": "claude-mono", "ext_hand": {"claude_accounts": {
                    "v1": {"config_dir": str(root / "c1")}, "v2": {"config_dir": str(root / "c2")}}}}))
            (root / "b.md").write_text("brief")
            env = {"HOME": tmp, "HYBRID_HANDS_CONFIG": str(root / "absent.json")}

            def fake_run(cfg, args):
                backend = get_backend(args.backend)
                spec = run_cmd._spec(cfg, args, backend, "p", root, "id-r2")
                captured.update(backend=backend.name, spec=spec, meta=run_cmd._write_meta(
                    root, CTX, spec, backend.name, "l", run_cmd._role_fields(args, "id-r2")))
                return 0

            with mock.patch.dict("os.environ", env, clear=True), \
                    mock.patch("hand_ext.run_cmd._cmd_shell_run", side_effect=fake_run), \
                    redirect_stderr(io.StringIO()):
                code = main(["run", "--cwd", tmp, "--brief", str(root / "b.md"), "--mode", "shell"]
                            + argv)
        return code, captured

    def test_collect_tier2_escalated(self):
        code, got = self.run_cli(["--role", "collect", "--tier", "2", "--escalated-from", "X"])
        self.assertEqual(code, 0)
        self.assertEqual(got["backend"], "claude-v1")
        self.assertIn("sonnet", got["spec"].model)
        self.assertEqual(got["spec"].effort, "medium")
        meta = got["meta"]
        self.assertEqual((meta["role"], meta["tier"], meta["attempt"], meta["escalated_from"],
                          meta["effort"]), ("collect", 2, 2, "X", "medium"))

    def test_no_role_defaults(self):
        code, got = self.run_cli(["--backend", "codex"])
        self.assertEqual((code, got["backend"]), (0, "codex"))
        meta = got["meta"]
        self.assertEqual((meta["role"], meta["tier"], meta["escalated_from"]), ("", None, None))

    def test_usage_errors(self):
        for argv in (["--tier", "2"], ["--role", "collect", "--backend", "codex"],
                     ["--role", "collect", "--tier", "1", "--escalated-from", "X"]):
            self.assertEqual(self.run_cli(argv)[0], 2, argv)


if __name__ == "__main__":
    unittest.main()
