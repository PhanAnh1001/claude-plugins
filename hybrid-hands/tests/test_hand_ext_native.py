"""Native pick policy using only temporary configuration and fake preflight."""
from __future__ import annotations

import io
import json
import tempfile
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from test_hand_ext_defaults import HandExtTestCase
from hand_ext.cli import cmd_pick
from hand_ext.config import load_config


class NativePickTest(HandExtTestCase):
    def pick(self, root: Path, section: dict) -> dict:
        global_config = root / "global.json"
        global_config.write_text(json.dumps({"ext_hand": section}))
        with mock.patch.dict("os.environ", {
                "HOME": str(root), "HYBRID_HANDS_CONFIG": str(global_config),
                "CLAUDECODE": "1", "CLAUDE_CONFIG_DIR": str(root / ".claude")}, clear=True), \
                mock.patch("hand_ext.cli.auto_preflight", return_value=[
                    (object(), "claude-v1", "")]):
            cfg = load_config(known_root=root, config_file=root / "absent.json")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cmd_pick(cfg, Namespace(json=True)), 0)
            return json.loads(output.getvalue())

    def test_global_native_claude_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.pick(Path(tmp), {"native": {"claude": "off"}})
        self.assertIs(result["native"], False)
        self.assertIn("off", result["native_reason"])

    def test_auto_same_account_effort_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.pick(Path(tmp), {"native": {"claude": "auto"},
                "backends": {"claude-v1": {"effort": "high"}}})
        self.assertIs(result["native"], False)
        self.assertIn("effort", result["native_reason"])
