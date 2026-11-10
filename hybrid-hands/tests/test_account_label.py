"""Unified account label: config first, then email local part; fixtures only."""
import json, os, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from account_label import account_label, backend_account_label, claude_email_name


class AccountLabelTest(unittest.TestCase):
    def test_config_plan_and_name_win(self):
        cfg = {"claude_accounts": {"v2": {"config_dir": "/nonexistent", "plan": "Max", "name": "foo"}},
               "gpt_accounts": {"v1": {"plan": "Plus"}}}
        self.assertEqual(account_label("claude", "v2", cfg, detected_plan="Pro"), "claude v2 Max foo")
        self.assertEqual(backend_account_label("codex", cfg), "gpt v1 Plus ?")
        bad = dict(cfg, account_label_format="{provider} {secret}")
        self.assertEqual(account_label("claude", "v2", bad), "claude v2 Max foo")

    @patch.dict(os.environ, {'HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE': ''})
    def test_name_from_email_local_part_or_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, broken, empty = (Path(tmp) / n for n in ("good", "broken", "empty"))
            for d in (good, broken, empty):
                d.mkdir()
            (good / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "foo.bar@example.com"}}))
            (broken / ".claude.json").write_text("{bad")
            cfg = {"claude_accounts": {"v3": {"config_dir": str(good)}}}
            self.assertEqual(account_label("claude", "v3", cfg, detected_plan="Max"), "claude v3 Max foo.bar")
            self.assertEqual((claude_email_name(str(broken)), claude_email_name(str(empty))), ("?", "?"))


if __name__ == "__main__":
    unittest.main()
