"""pick --role on temporary configuration only; day guard is faked."""
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


class PickRoleTest(unittest.TestCase):
    def pick(self, profile, argv, config_dir, session=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude/hybrid-hands.json").write_text(json.dumps({"profile": profile, "ext_hand": {
                "claude_accounts": {"v1": {"config_dir": str(root / "c1")},
                                    "v2": {"config_dir": str(root / "c2")}}}}))
            env = {"HOME": tmp, "HYBRID_HANDS_CONFIG": str(root / "absent.json"),
                   "CLAUDECODE": "1", "CLAUDE_CONFIG_DIR": str(root / config_dir),
                   "HYBRID_HANDS_STATE_DIR": str(root / "state"), "CLAUDE_CODE_SESSION_ID": "me"}
            if session:  # profile phiên "me" đã đặt; "other" là phiên khác
                (root / "state/session-profiles").mkdir(parents=True)
                (root / "state/session-profiles/claude-me.json").write_text(json.dumps({"profile": session[0]}))
                env["CLAUDE_CODE_SESSION_ID"] = session[1]
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict("os.environ", env, clear=True), \
                    mock.patch("hand_ext.run_cmd.day_guard", return_value=None), \
                    redirect_stdout(out), redirect_stderr(err):
                code = main(["pick", "--cwd", tmp, "--json"] + argv)
            return code, (json.loads(out.getvalue()) if code == 0 else err.getvalue())

    def test_claude_mono_collect_tiers_and_native(self):
        for tier, effort in (("1", "low"), ("2", "medium")):
            code, data = self.pick("claude-mono", ["--role", "collect", "--tier", tier], "c1")
            self.assertEqual(code, 0)
            self.assertEqual((data["backend"], data["agent_model"], data["effort"], data["native"]),
                             ("claude-v1", "sonnet", effort, True))
        code, data = self.pick("claude-mono", ["--role", "collect"], "c2")
        self.assertIs(data["native"], False)

    def test_gpt_mono_chrome_uses_claude_v2(self):
        code, data = self.pick("gpt-mono", ["--role", "chrome"], "c2")
        self.assertEqual((code, data["backend"], data["native"]), (0, "claude-v2", True))

    def test_session_profile_changes_pick_only_for_that_session(self):
        code, data = self.pick("gpt-mono", ["--role", "code"], "c2", ("claude-mono v2", "me"))
        self.assertEqual((code, data["backend"], data["profile"], data["native"]),
                         (0, "claude-v2", "claude-mono-v2", True))
        self.assertEqual(self.pick("gpt-mono", ["--role", "code"], "c2", ("claude-mono-v2", "other"))[1]["backend"],
                         "codex")

    def test_usage_errors(self):
        self.assertEqual(self.pick("claude-mono", ["--role", "code", "--tier", "1"], "c1")[0], 2)
        code, err = self.pick(None, ["--role", "code"], "c1")
        self.assertEqual(code, 2)
        self.assertIn("profile", err)


if __name__ == "__main__":
    unittest.main()
