"""hand-ext core: registry, auto fallback, quota state, caps, ledger locking."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "hand_ext"))

from codex_harness import Sandbox  # noqa: E402
from hand_ext import ledger  # noqa: E402
from hand_ext.backends import BackendUnavailable, get_backend  # noqa: E402
from hand_ext.backends.base import Backend, Check, Status  # noqa: E402

FAKE_MODULE = "hand_ext.backends.stubb"


class StubbBackend(Backend):
    """In-process second backend that always succeeds via `python3 -c`."""
    name = "stubb"

    def setup(self, options):
        return ["ok"]

    def doctor(self, options):
        return [Check("stub", True, "ok")]

    def build_command(self, spec):
        return [sys.executable, "-c", "print('stub done')"], {}, None

    def parse_line(self, line, state):
        state.final_text += line

    def finalize(self, spec, state, exit_code, stderr_text):
        return Status.OK if exit_code == 0 else Status.FAILED


def _register_stub() -> None:
    module = types.ModuleType(FAKE_MODULE)
    module.StubbBackend = StubbBackend
    sys.modules[FAKE_MODULE] = module


class BrowserCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sb = Sandbox(order=["codex", "dsh"])
        self.addCleanup(self.sb.close)
        path = self.sb.dir / ".claude" / "hybrid-hands.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        dsh_home = self.sb.dir / "dsh-home"
        config["ext_hand"]["backends"]["dsh"] = {
            "home": str(dsh_home), "key_file": str(dsh_home / "go.key")}
        path.write_text(json.dumps(config), encoding="utf-8")

    def test_explicit_backend_codex_with_browser_errors(self) -> None:
        code, out, err = self.sb.cli("run", "--brief", str(self.sb.brief),
                                     "--backend", "codex", "--browser")
        self.assertEqual(code, 2, (out, err))
        self.assertIn("--browser", err)
        self.assertIn("dsh", err)
        self.assertEqual(self.sb.ledger(), [])

    def test_auto_with_browser_only_considers_dsh(self) -> None:
        with mock.patch.dict(os.environ, {"HAND_EXT_DSH_BIN": "/nonexistent/dsh"}):
            code, out, err = self.sb.cli("run", "--brief", str(self.sb.brief), "--browser")
        self.assertEqual(code, 7, (out, err))
        self.assertIn("bỏ qua codex", err)
        self.assertIn("không hỗ trợ --browser", err)
        self.assertEqual(self.sb.ledger(), [])


class CoreTest(unittest.TestCase):
    def setUp(self) -> None:
        _register_stub()
        self.sb = Sandbox(order=["codex", "stubb"])
        # `status` reads the shared statusline cache: never point a test at the real ~/.claude.
        os.environ["CLAUDE_HOME"] = str(self.sb.dir / "claude-home")
        self.sb.cli("setup", "--backend", "codex")

    def tearDown(self) -> None:
        self.sb.close()

    def run_auto(self, *extra: str):
        return self.sb.cli("run", "--brief", str(self.sb.brief), *extra)

    def test_missing_backend_module(self) -> None:
        with self.assertRaises(BackendUnavailable):
            get_backend("nosuchcli")
        code, _, err = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "nosuchcli")
        self.assertEqual(code, 2)
        self.assertIn("chưa có", err)

    def test_auto_falls_back_on_quota_then_skips_exhausted(self) -> None:
        self.sb.scenario("quota")
        code, out, _ = self.run_auto()
        self.assertEqual(code, 0, out)
        self.assertEqual([e["backend"] for e in self.sb.ledger()], ["codex", "stubb"])
        self.assertIn("stub done", out)
        self.assertIn("exhausted_until", self.sb.quota()["codex"])
        code, _, err = self.run_auto()
        self.assertEqual(code, 0)
        self.assertIn("hết hạn mức tới", err)
        self.assertEqual([e["backend"] for e in self.sb.ledger()][-1], "stubb")

    def test_explicit_backend_does_not_fall_back(self) -> None:
        self.sb.scenario("quota")
        code, _, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex")
        self.assertEqual(code, 7)
        self.assertEqual(len(self.sb.ledger()), 1)

    def test_capped_by_tokens(self) -> None:
        self.sb.scenario("cap")
        code, _, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex",
                                 "--max-tokens", "3000")
        self.assertEqual(code, 4)
        entry = self.sb.ledger()[0]
        self.assertEqual(entry["status"], "capped")
        self.assertGreater(entry["tokens"]["input"] + entry["tokens"]["output"], 3000)

    def test_timeout(self) -> None:
        self.sb.scenario("hang")
        code, _, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex",
                                 "--timeout-min", "0.03")
        self.assertEqual(code, 6)
        self.assertEqual(self.sb.ledger()[0]["status"], "timeout")

    def test_status_and_report(self) -> None:
        self.sb.scenario("ok")
        self.run_auto("--label", "lab1")
        code, out, _ = self.sb.cli("status")
        self.assertEqual(code, 0)
        self.assertIn("| codex | đạt |", out)
        code, out, _ = self.sb.cli("report", "--backend", "codex")
        self.assertIn("Tổng lượt: 1", out)
        self.assertIn("lab1", out)


class LedgerTest(unittest.TestCase):
    def test_two_processes_append_without_loss(self) -> None:
        sb = Sandbox(order=["codex"])
        try:
            path = sb.dir / "ledger.json"
            lib = str(Path(ledger.__file__).resolve().parents[1])
            code = ("import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path;"
                    "from hand_ext import ledger\n"
                    "for i in range(40): ledger.append_entry(Path(sys.argv[2]), {'i': i})")
            procs = [subprocess.Popen([sys.executable, "-c", code, lib, str(path)]) for _ in range(2)]
            for p in procs:
                self.assertEqual(p.wait(timeout=60), 0)
            self.assertEqual(len(json.loads(path.read_text())), 80)
        finally:
            sb.close()


if __name__ == "__main__":
    unittest.main()
