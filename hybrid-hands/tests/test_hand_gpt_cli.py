"""End-to-end tests of bin/hand-gpt with a fake codex."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "plugins/hybrid-hands/bin/hand-gpt"
FAKE = ROOT / "tests/fixtures/hand_gpt/fake_codex.py"
SECRET = "sk-test-SECRET-should-never-print"
EXIT_NEEDS_APPROVAL = 3
EXIT_CAPPED = 4
EXIT_FLEX_REJECTED = 5


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.home = self.dir / "codex-home"
        (self.dir / ".claude").mkdir()
        (self.dir / ".claude/hybrid-hands.json").write_text(json.dumps(
            {"gpt_hand": {"codex_home": str(self.home), "max_usd": 0.3}}))
        self.brief = self.dir / "brief.md"
        self.brief.write_text("MỤC TIÊU: thử\nPHẠM VI GHI: CHỈ ĐỌC\n")
        self.argv_log = self.dir / "argv.json"

    def tearDown(self):
        self.tmp.cleanup()

    def hand(self, *args, scenario="ok", **env):
        full_env = dict(os.environ, HAND_GPT_CODEX_BIN=str(FAKE), FAKE_CODEX_SCENARIO=scenario,
                        FAKE_CODEX_ARGV_LOG=str(self.argv_log), **env)
        return subprocess.run([str(BIN), *args, "--cwd", str(self.dir)], capture_output=True,
                              text=True, env=full_env, timeout=120)

    def ledger(self):
        return json.loads((self.dir / "output/llm/codex_usage.json").read_text())

    def test_run_ok_records_usd_and_args(self):
        r = self.hand("run", "--brief", str(self.brief), "--label", "t1")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("status: ok", r.stdout)
        self.assertIn("usd: 0.2620", r.stdout)
        sent = json.loads(self.argv_log.read_text())
        self.assertIn('service_tier="flex"', sent["argv"])
        self.assertIn("gpt-6.1-sol", sent["argv"])
        self.assertIn("Luật hand", sent["prompt"])
        self.assertIn("MỤC TIÊU: thử", sent["prompt"])
        self.assertEqual(sent["codex_home"], str(self.home))
        entry = self.ledger()[0]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["tokens"], {"input": 200000, "cached_input": 40000, "output": 20000})

    def test_cap_stops_process(self):
        r = self.hand("run", "--brief", str(self.brief), scenario="cap")
        self.assertEqual(r.returncode, EXIT_CAPPED, r.stdout + r.stderr)
        self.assertIn("status: capped", r.stdout)
        usd = self.ledger()[0]["usd"]
        self.assertGreater(usd, 0.3)
        self.assertLess(usd, 1.0)  # stopped long before the fake's 300 steps

    def test_refuses_without_approval(self):
        r = self.hand("run", "--brief", str(self.brief), "--max-usd", "1.5")
        self.assertEqual(r.returncode, EXIT_NEEDS_APPROVAL)
        self.assertFalse(self.argv_log.exists())

    def test_flex_rejected_no_standard_retry(self):
        r = self.hand("run", "--brief", str(self.brief), scenario="flex")
        self.assertEqual(r.returncode, EXIT_FLEX_REJECTED, r.stdout + r.stderr)
        self.assertEqual([e["status"] for e in self.ledger()], ["flex_rejected"])

    def test_flex_rejected_allow_standard_retries_once(self):
        r = self.hand("run", "--brief", str(self.brief), "--allow-standard", scenario="flex")
        entries = self.ledger()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["tier"], "default")
        self.assertNotIn('service_tier="flex"', json.loads(self.argv_log.read_text())["argv"])
        self.assertNotEqual(r.returncode, 0)

    def test_estimate_table_and_approval_line(self):
        r = self.hand("estimate", "--brief", str(self.brief), "--max-usd", "2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gpt-6.1-sol / flex / medium", r.stdout)
        self.assertIn("developers.openai.com/api/docs/pricing", r.stdout)
        self.assertIn("Cần duyệt", r.stdout)

    def test_setup_idempotent(self):
        first = self.hand("setup")
        cfg = self.home / "config.toml"
        content = cfg.read_text()
        second = self.hand("setup")
        self.assertIn("đã ghi", first.stdout)
        self.assertIn("không đổi", second.stdout)
        self.assertEqual(cfg.read_text(), content)
        self.assertIn('service_tier = "flex"', content)
        self.assertFalse((self.home / "auth.json").exists())

    def test_doctor_never_prints_secret(self):
        self.hand("setup")
        (self.home / "auth.json").write_text(json.dumps(
            {"auth_mode": "apikey", "OPENAI_API_KEY": SECRET}))
        r = self.hand("doctor")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertIn("apikey", r.stdout)

    def test_doctor_old_codex_fails(self):
        self.hand("setup")
        r = self.hand("doctor", FAKE_CODEX_VERSION="0.150.1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("0.150.1", r.stdout)

    def test_report_aggregates(self):
        self.hand("run", "--brief", str(self.brief), "--label", "a")
        r = self.hand("report", "--label", "a")
        self.assertIn("| a | 1 |", r.stdout)


if __name__ == "__main__":
    unittest.main()
