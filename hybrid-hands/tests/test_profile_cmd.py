"""hand-ext profile on temporary configuration only."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hand_ext.cli import main


class ProfileCmdTest(unittest.TestCase):
    def test_set_show_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                "os.environ", {"HOME": tmp, "HYBRID_HANDS_CONFIG": str(Path(tmp) / "absent.json")}, clear=True):
            path = Path(tmp) / ".claude/hybrid-hands.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"side_session": {"codex_effort": "xhigh"}}))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["profile", "--cwd", tmp]), 2)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "set", "hybrid", "--cwd", tmp]), 0)
            self.assertEqual(json.loads(path.read_text()),
                             {"side_session": {"codex_effort": "xhigh"}, "profile": "hybrid"})
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["profile", "--cwd", tmp, "--json"]), 0)
            data = json.loads(out.getvalue())
            self.assertEqual((data["profile"], data["source"]), ("hybrid", "repo"))
            self.assertIn("super", data["roles"])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["profile", "set", "bogus", "--cwd", tmp])
            self.assertEqual(json.loads(path.read_text())["profile"], "hybrid")

    def test_set_with_account_and_session_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".claude/hybrid-hands.json"
            path.parent.mkdir()
            base = {"HOME": tmp, "HYBRID_HANDS_CONFIG": str(Path(tmp) / "absent.json"),
                    "HYBRID_HANDS_STATE_DIR": str(Path(tmp) / "state"), "CLAUDECODE": "1"}

            def run(argv, sid="s1"):
                out = io.StringIO()
                with mock.patch.dict("os.environ", {**base, "CLAUDE_CODE_SESSION_ID": sid}, clear=True), \
                        redirect_stdout(out), redirect_stderr(io.StringIO()):
                    return main(argv + ["--cwd", tmp]), out.getvalue()
            self.assertEqual(run(["profile", "set", "claude-mono", "v2"])[0], 0)
            self.assertEqual(json.loads(path.read_text())["profile"], "claude-mono-v2")
            run(["profile", "set", "claude-mono", "v1"])
            code, out = run(["profile", "session", "gpt-mono"])
            self.assertEqual(code, 0)
            self.assertIn("profile phiên = gpt-mono (claude-s1)", out)
            self.assertIn("config: claude-mono [repo]", out)
            data = json.loads(run(["profile", "--json"])[1])
            self.assertEqual((data["profile"], data["source"], data["config_profile"], data["session_key"]),
                             ("gpt-mono", "session", "claude-mono", "claude-s1"))
            self.assertEqual(json.loads(run(["profile", "--json"], sid="s2")[1])["source"], "repo")
            self.assertIn("profile phiên: gpt-mono", run(["profile", "session"])[1])
            self.assertEqual(run(["profile", "session", "--clear"])[0], 0)
            self.assertEqual(json.loads(run(["profile", "--json"])[1])["profile"], "claude-mono")
            self.assertEqual(json.loads(path.read_text())["profile"], "claude-mono")
            self.assertEqual(run(["profile", "session", "hybrid"], sid="bad/id")[0], 2)
            self.assertFalse(any((Path(tmp) / "state/session-profiles").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
