"""hand-ext ladder: log + stats on a temp JSONL via env; fixtures only."""
import argparse, contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hand_ext import ladder


def _call(*argv):
    parser = argparse.ArgumentParser()
    ladder.add_parser(parser.add_subparsers(dest="cmd"))
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = ladder.run(parser.parse_args(["ladder", *argv]), cfg={"profile": "p"})
    return code, out.getvalue().strip()


class LadderTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "ladder.jsonl"
        patcher = patch.dict(os.environ, {ladder.LADDER_FILE_ENV: str(self.path)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_escalation_stats(self):
        _call("log", "--role", "collect", "--tier", "1", "--result", "ok")
        _, failed = _call("log", "--role", "collect", "--tier", "1", "--result", "fail")
        code, _ = _call("log", "--role", "collect", "--tier", "2", "--result", "ok", "--escalated-from", failed)
        self.assertEqual(code, 0)
        with self.path.open("a") as f:
            f.write("{broken\n")
        _, out = _call("stats", "--json")
        data = json.loads(out)
        self.assertEqual(data["roles"]["collect"], {"tier1_runs": 2, "tier1_ok": 1, "tier1_ok_rate": 0.5,
                                                    "escalations": 1, "escalations_ok": 1, "tier2_fail": 0})
        self.assertEqual(data["skipped"], 1)

    def test_unknown_escalation_is_usage_and_not_written(self):
        code, _ = _call("log", "--role", "chrome", "--tier", "2", "--result", "ok", "--escalated-from", "nope")
        self.assertEqual(code, 2)
        self.assertFalse(self.path.exists())

    def test_missing_or_empty_file(self):
        self.assertEqual(_call("stats"), (0, _call("stats")[1]))
        self.assertIn(ladder.NO_DATA, _call("stats")[1])
        self.path.write_text("")
        code, out = _call("stats", "--json")
        self.assertEqual((code, json.loads(out)["roles"]["chrome"]["tier1_ok_rate"]), (0, None))
