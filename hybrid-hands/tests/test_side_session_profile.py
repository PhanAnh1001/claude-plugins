"""side-session start defaults come from the repo profile role."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'
sys.path.insert(0, str(LIB))
from shared_config import load_config
from side_session.profile_defaults import ProfileError, start_defaults

# Shared by side-session tests that build SideConfig directly (no config files).
GPT_MONO_FIXTURE = {"profile": "gpt-mono",
                    "ext_hand": {"gpt_accounts": {"v1": {}}, "claude_accounts": {"v1": {}, "v2": {}}}}


def patch_profile(actions_module):
    """Start a module-wide patch so `start` resolves gpt-mono without reading real config."""
    patcher = patch.object(actions_module.profile_defaults, "load_effective", return_value=GPT_MONO_FIXTURE)
    patcher.start()
    return patcher

NO_FLAGS = {"provider": None, "account": None, "model": None, "effort": None}


class SideSessionProfileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        env = patch.dict(os.environ, HOME=str(self.root), HYBRID_HANDS_CONFIG='global.json')
        env.start()
        self.addCleanup(env.stop)

    def cfg(self, profile=None):
        (self.root / 'global.json').write_text('{}')
        repo = self.root / 'repo.json'
        repo.write_text(json.dumps({"profile": profile} if profile else {}))
        return load_config(known_root=self.root, config_file=repo).effective

    def pick(self, profile, is_main, **flags):
        return start_defaults(self.cfg(profile), is_main, {**NO_FLAGS, **flags})

    def test_role_by_profile_and_session_kind(self):
        sol = {"provider": "codex", "account": None, "model": "gpt-6.1-sol", "effort": "high"}
        cases = [("hybrid", True, {"provider": "claude", "account": "v2",
                                   "model": "claude-opus-5-5", "effort": "high"}),
                 ("hybrid", False, sol), ("gpt-mono", True, sol),
                 ("claude-mono", True, {"provider": "claude", "account": "v1",
                                        "model": "claude-opus-5-5", "effort": "high"})]
        for profile, is_main, want in cases:
            with self.subTest(profile=profile, is_main=is_main):
                self.assertEqual(self.pick(profile, is_main), want)

    def test_flags_win_and_missing_profile_errors(self):
        got = self.pick("hybrid", True, model="claude-fable-5-2", effort="low")
        self.assertEqual((got["provider"], got["account"], got["model"], got["effort"]),
                         ("claude", "v2", "claude-fable-5-2", "low"))
        other = self.pick("hybrid", True, provider="codex")
        self.assertEqual((other["model"], other["effort"]), (None, None))
        with self.assertRaises(ProfileError):
            self.pick(None, True)


    def test_launch_env_carries_profile_role(self):
        from side_session import commands as K, profile_defaults
        from side_session.config import SideConfig
        cfg = SideConfig(self.root, self.root / 'h', self.root / 'wt', 2, 1000, 0)
        hybrid = self.cfg("hybrid")
        with patch.object(profile_defaults, "load_effective", return_value=hybrid):
            roles = [profile_defaults.resolve(self.root, m, NO_FLAGS)["role"] for m in (True, False)]
        self.assertEqual(roles, ["super", "brain"])
        _, env = K.provider_argv(cfg, "codex", "s", "u", str(self.root), "p", session_role="super")
        self.assertEqual(env["HYBRID_HANDS_ROLE"], "super")
        cmd = K.session_cmd(cfg, "claude", "s", "u", str(self.root), "p",
                            config_dir=str(self.root / 'v2'), session_role="brain")
        self.assertIn("HYBRID_HANDS_ROLE=brain", " ".join(cmd))


if __name__ == '__main__':
    unittest.main()
