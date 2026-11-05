"""Go usage ledger: cost estimate, sliding windows, `usage` command, status and run summary."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext import cli, go_usage, render, run_cmd  # noqa: E402
from hand_ext.backends.base import RunState, Status, Usage  # noqa: E402
from hand_ext.config import load_config  # noqa: E402
from hand_ext.runner import RunOutcome  # noqa: E402

MODEL = "deepseek-v4.1-flash"
PRICE = {"input": 1.0, "cached_input": 0.1, "output": 2.0}
MONTHLY_LIMIT = 100.0
NOW = 1_700_000_000.0
STATE_ENV = "HYBRID_HANDS_STATE_DIR"
TOKENS = {"input": 1000, "cached_input": 400, "output": 100}


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(epoch))


def record(ended: float, cost: float | None, source: str, model: str = MODEL) -> dict:
    return {"run_id": "r", "ended": iso(ended), "backend": "dsh", "model": model,
            "tokens": dict(TOKENS), "cost_usd": cost, "cost_source": source,
            "cwd_basename": "repo"}


class EstimateCostTest(unittest.TestCase):
    def test_uncached_input_plus_cached_plus_output(self) -> None:
        cost = go_usage.estimate_cost(TOKENS, PRICE)
        self.assertAlmostEqual(cost, (600 * 1.0 + 400 * 0.1 + 100 * 2.0) / 1_000_000)

    def test_missing_or_partial_price_gives_none(self) -> None:
        self.assertIsNone(go_usage.estimate_cost(TOKENS, None))
        self.assertIsNone(go_usage.estimate_cost(TOKENS, {}))
        self.assertIsNone(go_usage.estimate_cost(TOKENS, {"input": 1.0, "output": 2.0}))

    def test_cached_never_exceeds_input(self) -> None:
        tokens = {"input": 100, "cached_input": 500, "output": 10}
        self.assertAlmostEqual(go_usage.estimate_cost(tokens, PRICE),
                               (0 * 1.0 + 500 * 0.1 + 10 * 2.0) / 1_000_000)

    def test_build_record_stores_basename_only(self) -> None:
        built = go_usage.build_record("run-1", iso(NOW), "dsh", MODEL, TOKENS,
                                      0.5, "estimated", "/srv/example/secret/repo")
        self.assertEqual(built["cwd_basename"], "repo")
        self.assertNotIn("/srv/", json.dumps(built))

    def test_exact_allowance_wins_over_estimate(self) -> None:
        cost, source = go_usage.resolve_cost(TOKENS, 1.25, PRICE)
        self.assertEqual(cost, 1.25)
        self.assertEqual(source, "exact")

    def test_unknown_when_no_price_and_no_allowance(self) -> None:
        cost, source = go_usage.resolve_cost(TOKENS, None, None)
        self.assertIsNone(cost)
        self.assertEqual(source, "unknown")


class SummarizeTest(unittest.TestCase):
    def records(self) -> list[dict]:
        return [
            record(NOW - 3600, 2.0, "exact"),
            record(NOW - 5 * 3600, 1.0, "estimated"),
            record(NOW - 6 * 3600, 10.0, "exact"),
            record(NOW - 3 * 86400, 4.0, "exact"),
            record(NOW - 8 * 86400, 8.0, "exact"),
            record(NOW - 31 * 86400, 16.0, "exact"),
        ]

    def test_windows_and_boundaries(self) -> None:
        summary = go_usage.summarize(self.records(), MONTHLY_LIMIT, NOW)
        windows = summary["models"][MODEL]
        self.assertAlmostEqual(windows["5h"]["used_usd"], 3.0)
        self.assertAlmostEqual(windows["5h"]["limit_usd"], 20.0)
        self.assertAlmostEqual(windows["5h"]["percent"], 15.0)
        self.assertAlmostEqual(windows["7d"]["used_usd"], 17.0)
        self.assertAlmostEqual(windows["7d"]["limit_usd"], 50.0)
        self.assertAlmostEqual(windows["7d"]["percent"], 34.0)
        self.assertAlmostEqual(windows["30d"]["used_usd"], 25.0)
        self.assertAlmostEqual(windows["30d"]["limit_usd"], 100.0)
        self.assertAlmostEqual(windows["30d"]["percent"], 25.0)

    def test_old_record_just_outside_window_is_ignored(self) -> None:
        summary = go_usage.summarize(
            [record(NOW - 5 * 3600 - 1, 99.0, "exact")], MONTHLY_LIMIT, NOW)
        self.assertEqual(summary["models"][MODEL]["5h"]["used_usd"], 0.0)
        self.assertEqual(summary["updated_at"], int(NOW))

    def test_estimated_true_when_any_entry_is_not_exact(self) -> None:
        summary = go_usage.summarize(self.records(), MONTHLY_LIMIT, NOW)
        windows = summary["models"][MODEL]
        self.assertTrue(windows["5h"]["estimated"])
        self.assertTrue(windows["7d"]["estimated"])
        self.assertTrue(windows["30d"]["estimated"])

    def test_unknown_cost_counts_as_estimated(self) -> None:
        summary = go_usage.summarize(
            [record(NOW - 60, None, "unknown")], MONTHLY_LIMIT, NOW)
        window = summary["models"][MODEL]["5h"]
        self.assertEqual(window["used_usd"], 0.0)
        self.assertTrue(window["estimated"])

    def test_all_exact_is_not_estimated(self) -> None:
        summary = go_usage.summarize(
            [record(NOW - 60, 5.0, "exact")], MONTHLY_LIMIT, NOW)
        window = summary["models"][MODEL]["5h"]
        self.assertAlmostEqual(window["percent"], 25.0)
        self.assertFalse(window["estimated"])

    def test_summary_line_uses_estimated_mark(self) -> None:
        line = go_usage.summary_line(go_usage.summarize(self.records(), MONTHLY_LIMIT, NOW))
        self.assertEqual(line, "hạn mức: ~15% 5h, ~34% tuần (ước tính)")


class UsageCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.project = self.base / "project"
        (self.project / ".claude").mkdir(parents=True)
        (self.project / ".claude" / "hybrid-hands.json").write_text(json.dumps(
            {"ext_hand": {"order": [], "go_usage": {"monthly_limit_usd": MONTHLY_LIMIT}}}),
            encoding="utf-8")
        self.state = self.base / "state"
        self.state.mkdir()
        self.ledger = self.state / "go_usage.jsonl"
        self.now = time.time()
        self.ledger.write_text("\n".join(json.dumps(item) for item in (
            record(self.now - 600, 2.0, "estimated"),
            record(self.now - 2 * 86400, 3.0, "exact"),
        )) + "\n", encoding="utf-8")
        patcher = mock.patch.dict(os.environ, {
            STATE_ENV: str(self.state),
            "CLAUDE_HOME": str(self.base / "claude"),
            "HYBRID_HANDS_GO_FETCH": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.project)])
        return code, out.getvalue()

    def summary_path(self) -> Path:
        return self.state / "go_usage_summary.json"

    def test_usage_json_prints_and_writes_summary(self) -> None:
        code, out = self.cli("usage", "--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertIn(MODEL, data["models"])
        self.assertAlmostEqual(data["models"][MODEL]["5h"]["used_usd"], 2.0)
        written = json.loads(self.summary_path().read_text(encoding="utf-8"))
        self.assertEqual(written["models"][MODEL]["7d"]["used_usd"], 5.0)

    def test_usage_text_table(self) -> None:
        code, out = self.cli("usage")
        self.assertEqual(code, 0, out)
        self.assertIn(MODEL, out)
        self.assertIn("5h", out)
        self.assertIn("ước tính", out)
        self.assertIn("Console", out)

    def test_status_includes_go_percentages(self) -> None:
        self.assertEqual(self.cli("usage")[0], 0)
        code, out = self.cli("status")
        self.assertEqual(code, 0, out)
        self.assertIn("Go", out)
        self.assertIn("10%", out)
        self.assertIn("5%", out)


class RunSummaryTest(unittest.TestCase):
    def test_go_line_replaces_used_percent_none(self) -> None:
        entry = {"backend": "dsh", "model": MODEL, "status": "ok",
                 "tokens": dict(TOKENS), "quota": {"used_percent": None, "resets_at": None}}
        line = "hạn mức: ~15% 5h, ~34% tuần (ước tính)"
        text = render.run_summary(entry, 1.0, None, "", [], go_line=line)
        self.assertIn(line, text)
        self.assertNotIn("used_percent=None", text)


class GoConfigTest(unittest.TestCase):
    def test_custom_ledger_and_monthly_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".claude").mkdir()
            (project / ".claude" / "hybrid-hands.json").write_text(json.dumps(
                {"ext_hand": {"go_usage": {"ledger": "state/my.jsonl",
                                           "monthly_limit_usd": 200}}}), encoding="utf-8")
            cfg = load_config(project)
        self.assertEqual(cfg.go_usage_ledger.name, "my.jsonl")
        self.assertEqual(cfg.go_usage_summary.name, "my_summary.json")
        self.assertEqual(cfg.go_monthly_limit_usd, 200.0)

    def test_invalid_monthly_limit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".claude").mkdir()
            (project / ".claude" / "hybrid-hands.json").write_text(json.dumps(
                {"ext_hand": {"go_usage": {"monthly_limit_usd": 0}}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(project)


class RecordRunTest(unittest.TestCase):
    class Cfg:
        def __init__(self, base: Path) -> None:
            self.go_usage_ledger = base / "go_usage.jsonl"
            self.go_usage_summary = base / "go_usage_summary.json"
            self.go_monthly_limit_usd = MONTHLY_LIMIT
            self.go_usage_live = True

        def options(self, name: str) -> dict:
            return {"go_price_per_mtok": PRICE} if name == "dsh" else {}

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.cfg = self.Cfg(self.base)
        self.entry = {"run_id": "run-1", "ended": iso(NOW), "backend": "dsh",
                      "model": MODEL, "tokens": dict(TOKENS),
                      "cwd": "/srv/example/secret/repo"}
        patcher = mock.patch.dict(os.environ, {
            "CLAUDE_HOME": str(self.base / "claude"),
            "HYBRID_HANDS_GO_FETCH": "",
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_appends_estimated_cost_and_refreshes_summary(self) -> None:
        summary = go_usage.record_run(self.cfg, self.entry, now=NOW)
        lines = self.cfg.go_usage_ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        stored = json.loads(lines[0])
        self.assertEqual(stored["cost_source"], "estimated")
        self.assertEqual(stored["cwd_basename"], "repo")
        self.assertNotIn("/srv/", lines[0])
        self.assertTrue(self.cfg.go_usage_summary.is_file())
        self.assertEqual(summary["models"][MODEL]["5h"]["used_usd"], stored["cost_usd"])

    def test_exact_allowance_is_stored_as_exact(self) -> None:
        summary = go_usage.record_run(self.cfg, self.entry, exact_usd=1.5, now=NOW)
        stored = json.loads(self.cfg.go_usage_ledger.read_text(encoding="utf-8").strip())
        self.assertEqual(stored["cost_source"], "exact")
        self.assertEqual(stored["cost_usd"], 1.5)
        self.assertFalse(summary["models"][MODEL]["5h"]["estimated"])

    def test_run_hook_only_records_go_backends_and_returns_summary_line(self) -> None:
        outcome = RunOutcome(Status.OK, 0, RunState(usage=Usage(1000, 400, 100)), 1.0, [])
        line, extra = run_cmd._record_go(self.cfg, self.entry, outcome)
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("hạn mức: "))
        self.assertEqual(extra, [])
        self.assertEqual(len(self.cfg.go_usage_ledger.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(run_cmd._record_go(
            self.cfg, dict(self.entry, backend="codex"), outcome), (None, []))
        self.assertEqual(len(self.cfg.go_usage_ledger.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
