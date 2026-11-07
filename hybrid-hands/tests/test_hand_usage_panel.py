"""Public synthetic fixtures for pricing and absent account samples."""
import json
import os
import tempfile
from unittest.mock import patch
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))
sys.path.insert(0, str(TESTS / "fixtures" / "hh_ps"))
from fixture import HhFixture, MAIN_SESSION, NOW, iso
from hh_ps.render import render_json, render_text
from hh_ps.tree import build_snapshot
from hh_ps.usage_enrichment import enrich_snapshot
from hh_ps.models import Usage


class HandUsagePanelTest(unittest.TestCase):
    def snapshot(self):
        fx = HhFixture()
        self.addCleanup(fx.close)
        fx._run("priced-codex", backend="codex", model="gpt-6.1-sol",
                parent_session=MAIN_SESSION, status="ok", exit=0,
                started=iso(NOW - 180), ended=iso(NOW - 120),
                tokens={"input": 1_000_000, "cached_input": 400_000, "output": 500_000})
        with fx.env():
            return build_snapshot(fx.project, 6 * 3600, False, now=NOW)

    def test_finished_codex_cost_and_duration(self):
        snapshot = self.snapshot()
        next(run for run in snapshot.iter_runs() if run.run_id == "priced-codex").week_limit_usd = 50
        enrich_snapshot(snapshot, None, NOW)
        data = render_json(snapshot)
        run = next(run for session in data["sessions"] for run in session["hand_runs"]
                   if run["run_id"] == "priced-codex")
        self.assertTrue(run["usage"]["usd_estimated"])
        self.assertAlmostEqual(run["usage"]["usd"], 6.24)
        self.assertIsNotNone(run["ended_at"])
        self.assertEqual(run["duration_seconds"], 60)
        self.assertIsNone(run["usage"]["week_pct"])
        self.assertFalse(run["usage"]["week_pct_estimated"])

    def test_missing_quota_is_unknown(self):
        snapshot = self.snapshot()
        run = next(run for run in snapshot.iter_runs() if run.run_id == "priced-codex")
        self.assertIsNone(run.usage.account_5h_pct)
        self.assertIsNone(run.usage.account_week_pct)
        self.assertIn("?", render_text(snapshot))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": directory}):
            home = Path(directory)
            cache = home / ".statusline-cache.json"
            cache.write_text(json.dumps({"five": 23, "five_reset": NOW + 100}))
            os.utime(cache, (NOW, NOW))
            session = snapshot.sessions[0]
            session.provider, session.is_main, session.usage = "claude", False, None
            run.backend, run.tokens, run.usage = "claude-main", {}, None
            enrich_snapshot(snapshot, None, NOW)
            self.assertEqual(session.usage.account_5h_pct, 23)
            for invalid in (True, float("nan"), float("inf"), 101):
                cache.write_text(json.dumps({"five": invalid, "five_reset": NOW + 100}))
                os.utime(cache, (NOW, NOW))
                enrich_snapshot(snapshot, None, NOW)
                self.assertIsNone(session.usage.account_5h_pct)
            self.assertEqual(run.usage.account_plan, "Claude")
            self.assertIsNone(run.usage.usd)
            session.model, session.usage = "claude-opus-5-5", Usage(read=100, usd=None)
            enrich_snapshot(snapshot, None, NOW + 101)
            self.assertIsNone(session.usage.usd)
            self.assertIsNone(session.usage.account_5h_pct)
