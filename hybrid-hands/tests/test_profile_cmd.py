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


if __name__ == "__main__":
    unittest.main()
