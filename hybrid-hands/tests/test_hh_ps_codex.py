"""`hh-ps` Codex rows: ledger USD, pinned-rollout Sol USD and GPT account samples."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))
sys.path.insert(0, str(TESTS / "fixtures" / "hh_ps"))

from fixture import HhFixture, MAIN_SESSION, NOW, iso  # noqa: E402
from hh_ps import codex  # noqa: E402
from hh_ps.render import render_json, render_text  # noqa: E402
from hh_ps.tree import build_snapshot  # noqa: E402

SOL_SIDE = "b2c4d6e8-0a1c-4e3f-8a5b-6c7d8e9f0a1b"
HAND_RUN = "codex-hand-run"
SOL_USD = 6.24


class CodexPanelTest(unittest.TestCase):
    def test_codex_usd_pct_samples_and_gpt_account_limits(self) -> None:
        fx = HhFixture()
        self.addCleanup(fx.close)
        day = fx.home / ".codex-hand" / "sessions" / "2026" / "11" / "07"
        day.mkdir(parents=True)
        rollout = day / "rollout-2026-11-07T00-00-00-sol.jsonl"
        rollout.write_text("\n".join([
            json.dumps({"type": "session_meta", "payload": {"id": "sol"}}),
            # A conversation record carrying the old hint words must not be parsed as usage.
            json.dumps({"type": "response_item", "payload": {
                "type": "message", "text": "event_msg", "sentinel": "999999999",
                "other": "token_count", "limits": "rate_limits"}}),
            # Live rollouts put numeric metadata `ordinal` between timestamp and type.
            json.dumps({"timestamp": iso(NOW - 60), "ordinal": 20, "type": "event_msg", "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {
                    "input_tokens": 1_000_000, "cached_input_tokens": 400_000,
                    "output_tokens": 500_000}},
                "rate_limits": {
                    "primary": {"used_percent": 44, "window_minutes": 300,
                                "resets_at": NOW + 3600},
                    "secondary": {"used_percent": 55, "window_minutes": 10080,
                                  "resets_at": NOW + 2 * 86400},
                    "plan_type": "pro"}}}),
            '{"type":"event_msg","payload":{"type":"token_count"',
        ]) + "\n", encoding="utf-8")
        # The old ~/.codex account must never contribute a sample.
        old = fx.home / ".codex" / "sessions" / "2026" / "11" / "07"
        old.mkdir(parents=True)
        (old / "rollout-old.jsonl").write_text(json.dumps({
            "type": "event_msg", "timestamp": iso(NOW), "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"input_tokens": 7_000_000,
                                               "output_tokens": 0}},
                "rate_limits": {"primary": {"used_percent": 97, "window_minutes": 300,
                                            "resets_at": NOW + 3600}}},
        }) + "\n", encoding="utf-8")

        tokens = {"input": 1_000_000, "cached_input": 400_000, "output": 500_000}
        (fx.state / "codex_usage.jsonl").write_text("\n".join([
            json.dumps({
                "schema": 1, "run_id": HAND_RUN, "ended": iso(NOW - 120),
                "model": "gpt-6.1-sol", "effort": "low", "tokens": tokens,
                "cost_usd": 1.25, "cost_source": "estimated",
                "codex_home": ".codex-hand",
                "windows": {
                    "5h": {"used_percent": 12.5, "resets_at": iso(NOW + 1800)},
                    "7d": {"used_percent": 34.0, "resets_at": iso(NOW + 2 * 86400)},
                }}),
            json.dumps({"schema": 1, "run_id": "old-account", "ended": iso(NOW),
                        "codex_home": ".codex", "cost_usd": 999,
                        "tokens": tokens, "windows": {}}),
            '{"schema":1,"run_id":"broken"',
        ]) + "\n", encoding="utf-8")
        fx._run(HAND_RUN, backend="codex", model="gpt-6.1-sol",
                parent_session=MAIN_SESSION, status="ok", exit=0,
                started=iso(NOW - 180), ended=iso(NOW - 120), tokens=tokens)
        (fx.project / "output" / "state" / "sol-side.json").write_text(json.dumps({
            "name": "sol-side", "uuid": SOL_SIDE, "provider": "codex",
            "dir": str(fx.project), "screen": "sol", "watch_screen": "sol-watch",
            "max_tokens": 300000, "started": NOW - 300, "status": "running",
            "handoff": "", "tokens_used": 0, "worktree": False,
            "parent_session": MAIN_SESSION, "codex_rollout": str(rollout),
        }), encoding="utf-8")

        with fx.env(), mock.patch.object(codex.json, "loads", wraps=json.loads) as spy:
            snapshot = build_snapshot(fx.project, 6 * 3600, False, now=NOW)
        data = render_json(snapshot)
        text = render_text(snapshot)

        parsed_lines = [call.args[0] for call in spy.call_args_list if call.args]
        self.assertFalse(any('"response_item"' in str(line) for line in parsed_lines),
                         "conversation records must never reach json.loads")

        gpt = {row["window"]: row for row in data["limits"] if row["plan"] == "GPT"}
        self.assertEqual(set(gpt), {"5h", "tuần"})
        self.assertEqual((gpt["5h"]["total_pct"], gpt["tuần"]["total_pct"]), (44, 55))
        self.assertEqual(gpt["5h"]["source"], "codex_rollout")
        self.assertIsNone(gpt["5h"]["this_machine_pct"])
        self.assertTrue(gpt["5h"]["resets_at"])

        sessions = {item["session_id"]: item for item in data["sessions"]}
        hand = next(run for run in sessions[MAIN_SESSION]["hand_runs"]
                    if run["run_id"] == HAND_RUN)["usage"]
        self.assertEqual(hand["usd"], 1.25)
        self.assertTrue(hand["usd_estimated"])
        self.assertEqual((hand["gpt_5h_pct"], hand["gpt_week_pct"]), (12.5, 34.0))
        sol = sessions[SOL_SIDE]["usage"]
        self.assertAlmostEqual(sol["usd"], SOL_USD, places=6)
        self.assertEqual((sol["read"], sol["cache_read"], sol["out"]),
                         (600_000, 400_000, 500_000))
        self.assertEqual((sol["gpt_5h_pct"], sol["gpt_week_pct"]), (44, 55))
        self.assertIn("~$1.25", text)
        self.assertIn("~$6.24", text)
        self.assertIn("GPT 5h 12.5% · tuần 34.0%", text)
        self.assertIn("GPT 5h 44.0% · tuần 55.0%", text)
        self.assertRegex(text, r"GPT 5h\s+tổng 44\.0% · reset \d\d:\d\d")
        self.assertNotIn("97.0%", text)
        self.assertNotIn("999999999", text)


if __name__ == "__main__":
    unittest.main()
