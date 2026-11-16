"""hand-ext core: registry, explicit backend, quota state, caps, ledger locking."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "hand_ext"))

from codex_harness import Sandbox  # noqa: E402
from hand_ext import ledger  # noqa: E402
from hand_ext.backends import BackendUnavailable, get_backend  # noqa: E402
from hand_ext_case import HandExtTestCase  # noqa: E402

class CoreTest(HandExtTestCase):
    def setUp(self) -> None:
        self.sb = Sandbox()
        # `status` reads the shared statusline cache: never point a test at the real ~/.claude.
        os.environ["CLAUDE_HOME"] = str(self.sb.dir / "claude-home")
        self.sb.cli("setup", "--backend", "codex")

    def tearDown(self) -> None:
        self.sb.close()

    def run_codex(self, *extra: str):
        return self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex", *extra)

    def test_missing_backend_module(self) -> None:
        with self.assertRaises(BackendUnavailable):
            get_backend("nosuchcli")
        code, _, err = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "nosuchcli")
        self.assertEqual(code, 2)
        self.assertIn("chưa có", err)

    def test_run_without_role_or_backend_is_usage_error(self) -> None:
        for extra in ((), ("--backend", "auto")):
            code, _, err = self.sb.cli("run", "--brief", str(self.sb.brief), *extra)
            self.assertEqual(code, 2)
            self.assertIn("cần --role code|collect|chrome hoặc --backend <tên>", err)
        self.assertEqual(self.sb.ledger(), [])

    def test_explicit_backend_does_not_fall_back(self) -> None:
        self.sb.scenario("quota")
        code, _, err = self.run_codex()
        self.assertEqual(code, 7)
        self.assertEqual([e["backend"] for e in self.sb.ledger()], ["codex"])
        self.assertIn("không tự chuyển backend", err)

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
        self.run_codex("--label", "lab1")
        run_dir = next((self.sb.dir / "output" / "llm" / "hand-ext").iterdir())
        self.assertEqual((run_dir / "brief.md").read_text(encoding="utf-8"),
                         self.sb.brief.read_text(encoding="utf-8"))
        prompt = (run_dir / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(self.sb.brief.read_text(encoding="utf-8").strip(), prompt)
        code, out, _ = self.sb.cli("status")
        self.assertEqual(code, 0)
        self.assertIn("| codex | đạt |", out)
        code, out, _ = self.sb.cli("report", "--backend", "codex")
        self.assertIn("Tổng lượt: 1", out)
        self.assertIn("lab1", out)


class LedgerTest(HandExtTestCase):
    def test_two_processes_append_without_loss(self) -> None:
        sb = Sandbox()
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
