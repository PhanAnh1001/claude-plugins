"""Tests for scripts/week_split.py: solo windows, USD-per-% calibration, split and sessions."""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import week_split as ws  # noqa: E402

TODAY = date(2026, 11, 6)  # a Friday (T6)
YESTERDAY = TODAY - timedelta(days=1)
NOW = ws.at(TODAY, "15:00")
RESET = NOW + 3 * 86400
PERF_LIMIT_SECONDS = 2.0


def ledger_of(rows: list[tuple[float, float, str]], sessions: dict | None = None) -> dict:
    return {"messages": {f"m{i}|r": [ts, usd, sid] for i, (ts, usd, sid) in enumerate(rows)},
            "sessions": sessions or {}, "unpriced": {}}


class SoloWindowTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = Path(tmp.name) / ws.SOLO_WINDOWS_NAME

    def test_defaults_include_overnight_from_previous_day(self) -> None:
        windows = ws.solo_windows(self.config, NOW)
        self.assertEqual(len(windows), 2 * (ws.LOOKBACK_DAYS + 1))
        self.assertIn(ws.Window(ws.at(YESTERDAY, "21:00"), ws.at(TODAY, "07:00")), windows)
        self.assertIn(ws.Window(ws.at(TODAY, "12:00"), ws.at(TODAY, "13:30")), windows)

    def test_unfinished_window_dropped(self) -> None:
        windows = ws.solo_windows(self.config, ws.at(TODAY, "12:30"))
        self.assertNotIn(ws.Window(ws.at(TODAY, "12:00"), ws.at(TODAY, "13:30")), windows)

    def test_daily_line_replaces_defaults(self) -> None:
        self.config.write_text("# comment\n\ndaily 09:00-10:00\n")
        windows = ws.solo_windows(self.config, NOW)
        self.assertEqual(len(windows), ws.LOOKBACK_DAYS + 1)
        self.assertTrue(all(w.end - w.start == 3600 for w in windows))

    def test_one_day_window_replaces_nested_daily(self) -> None:
        self.config.write_text(f"{YESTERDAY.isoformat()} 11:00-14:00\n")
        windows = ws.solo_windows(self.config, NOW)
        self.assertIn(ws.Window(ws.at(YESTERDAY, "11:00"), ws.at(YESTERDAY, "14:00")), windows)
        self.assertNotIn(ws.Window(ws.at(YESTERDAY, "12:00"), ws.at(YESTERDAY, "13:30")), windows)


class CalibrationTest(unittest.TestCase):
    window = ws.Window(ws.at(TODAY, "12:00"), ws.at(TODAY, "13:30"))

    def rate(self, samples: list[ws.Sample], usd: float) -> ws.Rate:
        index = ws.UsdIndex(ledger_of([(self.window.start + 600, usd, "s")])["messages"])
        return ws.calibrate(samples, index, [self.window])

    def test_calibrates_from_solo_window(self) -> None:
        samples = [ws.Sample(self.window.start + 60, 10, RESET),
                   ws.Sample(self.window.start + 1200, 13, RESET)]
        self.assertEqual(self.rate(samples, 30.0), ws.Rate(10.0, ws.RATE_CALIB, 1))

    def test_pin_file_wins_over_calibration(self) -> None:
        samples = [ws.Sample(self.window.start + 60, 10, RESET),
                   ws.Sample(self.window.start + 1200, 13, RESET)]
        index = ws.UsdIndex(ledger_of([(self.window.start + 600, 30.0, "s")])["messages"])
        with tempfile.TemporaryDirectory() as tmp:
            pin_file = Path(tmp) / ws.USD_PER_PCT_PIN_NAME
            pin_file.write_text("# ghim\n13.74\n")
            pin = ws.load_pin(pin_file)
        self.assertEqual(ws.calibrate(samples, index, [self.window], pin),
                         ws.Rate(13.74, ws.RATE_PIN, 0))

    def test_small_delta_falls_back_to_prior(self) -> None:
        samples = [ws.Sample(self.window.start + 60, 10, RESET),
                   ws.Sample(self.window.start + 1200, 11, RESET)]
        self.assertEqual(self.rate(samples, 30.0), ws.Rate(ws.PRIOR_USD_PER_PCT, ws.RATE_PRIOR, 0))

    def test_last_sample_must_share_reset(self) -> None:
        samples = [ws.Sample(self.window.start + 60, 10, RESET),
                   ws.Sample(self.window.start + 1200, 13, RESET),
                   ws.Sample(self.window.start + 1800, 1, RESET + 86400)]
        self.assertEqual(self.rate(samples, 30.0).label, ws.RATE_CALIB)

    def test_no_samples_in_window_is_prior(self) -> None:
        self.assertEqual(self.rate([ws.Sample(NOW, 10, RESET)], 30.0).label, ws.RATE_PRIOR)


class SplitTest(unittest.TestCase):
    def test_local_other_and_days(self) -> None:
        start = RESET - ws.WEEK_SECONDS
        ledger = ledger_of([(start - 100, 99.0, "s"), (ws.at(YESTERDAY, "09:00"), 6.0, "s"),
                            (ws.at(TODAY, "09:00"), 12.0, "s")])
        summary = ws.build_summary([ws.Sample(NOW, 4, RESET)], ledger, NOW, [])
        self.assertEqual(summary["version"], 2)
        self.assertEqual((summary["usd_per_pct"], summary["rate_label"]), (12.0, "prior"))
        self.assertAlmostEqual(summary["local_usd"], 18.0)
        self.assertEqual((summary["local"], summary["other"]), (1.5, 2.5))
        days = {d["wd"]: d["pct"] for d in summary["days"]}
        self.assertEqual((days["T5"], days["T6"]), (0.5, 1.0))
        self.assertEqual(summary["days"][-1]["wd"], "T6")

    def test_other_never_negative(self) -> None:
        ledger = ledger_of([(NOW - 60, 120.0, "s")])
        summary = ws.build_summary([ws.Sample(NOW, 4, RESET)], ledger, NOW, [])
        self.assertEqual((summary["local"], summary["other"]), (10.0, 0.0))

    def test_no_samples_no_summary(self) -> None:
        self.assertIsNone(ws.build_summary([], ledger_of([]), NOW, []))


class SessionTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "sub").mkdir()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"side_session": {"state_dir": "custom/state"}}))
        state = self.repo / "custom" / "state"
        state.mkdir(parents=True)
        for name, uuid, provider, parent in (("b", "B", "claude", "A"), ("c", "C", "claude", "B"),
                                             ("d", "D", "codex", "A"), ("e", "E", "claude", "")):
            (state / f"{name}.json").write_text(json.dumps(
                {"uuid": uuid, "provider": provider, "parent_session": parent}))
        (state / "broken.json").write_text("{")

    def test_nested_side_sessions_roll_up(self) -> None:
        cwd = str(self.repo / "sub")
        sessions = {sid: {"cwd": cwd, "last_ts": NOW} for sid in "BCDE"}
        ledger = ledger_of([(NOW - 60, 12.0, "B"), (NOW - 60, 24.0, "C"), (NOW - 60, 12.0, "D"),
                            (NOW - 60, 6.0, "E")], sessions)
        result = ws.session_totals(ledger, NOW - 3600, 12.0)
        self.assertEqual(result["A"], {"usd": 0.0, "total_usd": 36.0, "pct": 3.0})
        self.assertEqual(result["B"]["total_usd"], 36.0)
        self.assertEqual(result["C"]["total_usd"], 24.0)
        self.assertEqual(result["D"]["total_usd"], 12.0)  # codex child not rolled into A
        self.assertEqual(result["E"]["total_usd"], 6.0)

    def test_cycle_is_safe(self) -> None:
        state = self.repo / "custom" / "state"
        (state / "loop.json").write_text(json.dumps(
            {"uuid": "A", "provider": "claude", "parent_session": "C"}))
        ledger = ledger_of([(NOW - 60, 12.0, "B")], {"B": {"cwd": str(self.repo), "last_ts": NOW}})
        result = ws.session_totals(ledger, NOW - 3600, 12.0)
        self.assertEqual(result["A"]["total_usd"], 12.0)

    def test_default_state_dir_without_config(self) -> None:
        (self.repo / ".claude" / "hybrid-hands.json").unlink()
        self.assertEqual(ws.side_state_dir(self.repo), self.repo / ws.DEFAULT_SIDE_STATE_DIR)


class PerformanceTest(unittest.TestCase):
    def test_build_summary_scales(self) -> None:
        start = RESET - ws.WEEK_SECONDS
        rows = [(start + i * 12.0, 0.01, f"s{i % 50}") for i in range(50_000)]
        samples = [ws.Sample(start + i * 300.0, i / 100, RESET) for i in range(2_000)]
        windows = ws.solo_windows(Path("/nonexistent"), NOW)
        began = time.perf_counter()
        summary = ws.build_summary(samples, ledger_of(rows), NOW, windows)
        self.assertLess(time.perf_counter() - began, PERF_LIMIT_SECONDS)
        self.assertIsNotNone(summary)


class RunTest(unittest.TestCase):
    def test_run_writes_summary_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            now = time.time()
            (home / ws.SAMPLES_NAME).write_text(f"{now - 10:.0f}\t15\t{now + 3600:.0f}\n")
            ws.run(home, now)
            summary = json.loads((home / ws.SUMMARY_NAME).read_text())
            self.assertEqual((summary["version"], summary["total"]), (2, 15))
            self.assertFalse((home / ws.LOCK_NAME).exists())

    def test_fresh_lock_skips_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ws.LOCK_NAME).mkdir()
            (home / ws.SAMPLES_NAME).write_text(f"{time.time():.0f}\t15\t1\n")
            ws.run(home, time.time())
            self.assertFalse((home / ws.SUMMARY_NAME).exists())


if __name__ == "__main__":
    unittest.main()
