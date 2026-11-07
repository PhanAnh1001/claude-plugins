"""codex backend of hand-ext: env scrubbing, rollout usage/quota, setup, doctor."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "hand_ext"))

from codex_harness import SECRET, Sandbox  # noqa: E402
from hand_ext.backends.codex import quota_from_rate_limits  # noqa: E402
from hand_ext.backends.codex_config import merge_top_level  # noqa: E402

OLD_CONFIG = ('model = "gpt-6.1-sol"\nservice_tier = "flex"\nmodel_reasoning_effort = "medium"\n'
              'sandbox_mode = "workspace-write"\n\n[mcp_servers.x]\ncommand = "y"\n')


class CodexRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sb = Sandbox(order=["codex"])

    def tearDown(self) -> None:
        self.sb.close()

    def test_ok_run_scrubs_api_keys_and_reads_rollout(self) -> None:
        self.sb.scenario("ok")
        code, out, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex")
        self.assertEqual(code, 0, out)
        logged = json.loads(self.sb.log.read_text())
        self.assertEqual(logged["env_keys"], [])
        self.assertEqual(logged["codex_home"], str(self.sb.home))
        self.assertIn("--skip-git-repo-check", logged["argv"])
        self.assertNotIn("--ephemeral", logged["argv"])
        self.assertNotIn("service_tier", " ".join(logged["argv"]))
        self.assertIn("## BRIEF", logged["prompt"])
        entry = self.sb.ledger()[0]
        self.assertEqual(entry["tokens"], {"input": 2000, "cached_input": 400, "output": 200})
        self.assertEqual(entry["quota"]["used_percent"], 42)
        self.assertNotIn("usd", entry)
        self.assertIn("BÁO CÁO GIẢ", out)
        self.assertNotIn(SECRET, out)

    def test_quota_message_marks_exhausted(self) -> None:
        self.sb.scenario("quota")
        code, _, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex")
        self.assertEqual(code, 7)
        self.assertEqual(self.sb.ledger()[0]["status"], "quota_exhausted")
        self.assertTrue(self.sb.quota()["codex"]["exhausted_until"].startswith("2100-01-01"))

    def test_not_logged_in(self) -> None:
        self.sb.scenario("login")
        code, _, _ = self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "codex")
        self.assertEqual(code, 7)
        self.assertEqual(self.sb.ledger()[0]["status"], "not_logged_in")

    def test_usage_ledger_keeps_both_windows_and_estimates_once(self) -> None:
        home = self.sb.dir / "home"
        home.mkdir()
        config_path = self.sb.dir / ".claude" / "hybrid-hands.json"
        config = json.loads(config_path.read_text())
        backend = config["ext_hand"]["backends"]["codex"]
        backend["price_per_mtok"] = {"input": 1.0, "cached": 0.1, "output": 2.0}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop("HYBRID_HANDS_STATE_DIR", None)
            ledger = home / ".hybrid-hands" / "codex_usage.jsonl"
            for scenario in ("ok", "weekly"):
                self.sb.scenario(scenario)
                code, out, _ = self.sb.cli("run", "--brief", str(self.sb.brief),
                                           "--backend", "codex")
                self.assertEqual(code, 0, out)
                backend["price_per_mtok"] = None  # explicit null -> unknown
                config_path.write_text(json.dumps(config), encoding="utf-8")
            lines = ledger.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        first, second = (json.loads(line) for line in lines)
        self.assertEqual(first["tokens"], {"input": 2000, "cached_input": 400, "output": 200})
        self.assertAlmostEqual(first["cost_usd"], 0.00204)
        self.assertEqual(first["cost_source"], "estimated")
        self.assertEqual(first["windows"]["5h"], {
            "used_percent": 42.0, "resets_at": "2100-01-01T00:00:00+00:00"})
        self.assertEqual(first["windows"]["7d"], {
            "used_percent": 10.0, "resets_at": "2100-01-01T00:00:01+00:00"})
        self.assertEqual(first["codex_home"], self.sb.home.name)
        self.assertEqual((first["model"], first["effort"]), ("gpt-6.1-sol", "high"))
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertIsNone(second["cost_usd"])
        self.assertEqual(second["cost_source"], "unknown")
        self.assertIsNone(second["windows"]["5h"])
        self.assertEqual(second["windows"]["7d"], {
            "used_percent": 3.0, "resets_at": "2100-01-01T00:00:01+00:00"})
        text = "\n".join(lines)
        for banned in (str(self.sb.home), str(self.sb.dir), "prompt", "report"):
            self.assertNotIn(banned, text)


class CodexSetupDoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sb = Sandbox(order=["codex"])

    def tearDown(self) -> None:
        self.sb.close()

    def test_setup_drops_service_tier_idempotent(self) -> None:
        cfg = self.sb.home / "config.toml"
        cfg.write_text(OLD_CONFIG)
        code, out, _ = self.sb.cli("setup", "--backend", "codex")
        self.assertEqual(code, 0)
        self.assertIn("đã ghi", out)
        text = cfg.read_text()
        self.assertNotIn("service_tier", text)
        self.assertIn('model_reasoning_effort = "high"', text)
        self.assertIn("[mcp_servers.x]", text)
        self.assertIn("--device-auth", out)
        _, out2, _ = self.sb.cli("setup", "--backend", "codex")
        self.assertIn("không đổi", out2)
        self.assertEqual(cfg.read_text(), text)

    def test_merge_keeps_tables(self) -> None:
        merged = merge_top_level(OLD_CONFIG, {"model": "m"})
        self.assertTrue(merged.startswith('model = "m"\n'))
        self.assertIn('command = "y"', merged)

    def test_doctor_ready_without_printing_secret(self) -> None:
        self.sb.cli("setup", "--backend", "codex")
        code, out, _ = self.sb.cli("doctor", "--backend", "codex")
        self.assertEqual(code, 0, out)
        self.assertIn("chatgpt", out)
        self.assertNotIn(SECRET, out)

    def test_doctor_rejects_api_key_login(self) -> None:
        (self.sb.home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": SECRET}))
        self.sb.cli("setup", "--backend", "codex")
        code, out, _ = self.sb.cli("doctor", "--backend", "codex")
        self.assertEqual(code, 1)
        self.assertIn("API key", out)
        self.assertNotIn(SECRET, out)

    def test_quota_picks_fullest_window(self) -> None:
        q = quota_from_rate_limits({"primary": {"used_percent": 30, "resets_at": 0},
                                    "secondary": {"used_percent": 100, "resets_at": 60}})
        self.assertEqual((q.used_percent, q.window, q.exhausted), (100.0, "secondary", True))
        self.assertEqual(q.resets_at, "1970-01-01T00:01:00+00:00")


if __name__ == "__main__":
    unittest.main()
