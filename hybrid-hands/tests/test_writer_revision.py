"""Plugin state writers bump the hh-store revision after a successful write."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN_LIB = Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))

from hand_ext.execution_state import atomic_json  # noqa: E402
from hh_store import read_revision  # noqa: E402
from side_session.state import SessionState, save  # noqa: E402

STATE_ENV = "HYBRID_HANDS_STATE_DIR"


def _side_state() -> SessionState:
    return SessionState(name="demo", uuid="u", provider="codex", dir="/x", screen="s",
                        watch_screen="w", max_tokens=1, started=0.0, status="running", handoff="")


class WriterRevisionTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = self.root / "store"

    def test_successful_writes_bump_revision(self) -> None:
        with mock.patch.dict(os.environ, {STATE_ENV: str(self.store)}):
            save(self.root / "side", _side_state())
            self.assertEqual(read_revision(self.store), 1)
            atomic_json(self.root / "exec.json", {"a": 1})
            self.assertEqual(read_revision(self.store), 2)

    def test_broken_revision_dir_does_not_break_writer(self) -> None:
        blocker = self.root / "plain-file"
        blocker.write_text("x")
        with mock.patch.dict(os.environ, {STATE_ENV: str(blocker)}):
            save(self.root / "side", _side_state())
        self.assertTrue((self.root / "side" / "demo.json").is_file())


if __name__ == "__main__":
    unittest.main()
