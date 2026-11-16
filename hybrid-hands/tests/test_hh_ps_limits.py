"""`hh-ps` weekly limits: statusline formulas, stale caches and per-row percentages.

Cross-checked against the statusline plugin itself:
- `week_split.build_summary` / `session_totals` / `estimate_week`
  (statusline/plugins/statusline/scripts/week_split.py:256, 332, 359)
"""
from __future__ import annotations

__import__("os").environ["HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"] = "1"  # never read real account files
import json
import hashlib
import os
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))
STATUSLINE = TESTS.parent.parent / "statusline" / "plugins" / "statusline" / "scripts"
sys.path.insert(0, str(STATUSLINE))

import week_split  # noqa: E402

from hh_ps.limits import collect_limits  # noqa: E402
from hh_ps.models import Session, Snapshot, Usage  # noqa: E402
from hh_ps.render import render_json  # noqa: E402
from hh_ps.timeutil import iso_at, percent_text  # noqa: E402
from hh_ps.tree import build_snapshot  # noqa: E402
from usage_pricing import load_prices
from hh_ps.week import STATUSLINE_LEDGER_ENV, claude_pct, read_claude_week  # noqa: E402

NOW = 1_800_000_000.0
HOUR = 3600.0
DAY = 86400.0
MODEL = "deepseek-v4.1-flash"
RESET = NOW + DAY
STATUSLINE_LEDGER = STATUSLINE / "usage_ledger.py"


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_CALIBRATION_PATCHES: List[Any] = []
_CALIBRATION_STATE: List[Path] = []


def setUpModule() -> None:
    """build_snapshot enriches with Claude calibration: keep its caches in a temp dir, never poll."""
    from unittest.mock import patch
    from hh_ps import claude_calibration
    state = Path(tempfile.mkdtemp(prefix="hh-ps-limits-calibration-"))
    _CALIBRATION_STATE.append(state)
    _CALIBRATION_PATCHES.extend([
        patch.object(claude_calibration, "cache_path", return_value=state / "calibration.json"),
        patch.object(claude_calibration, "auth_cache_path", return_value=state / "auth.json"),
        patch.object(claude_calibration, "command", side_effect=OSError("no real CLI in tests")),
    ])
    for item in _CALIBRATION_PATCHES:
        item.start()


def tearDownModule() -> None:
    for item in _CALIBRATION_PATCHES:
        item.stop()
    __import__("shutil").rmtree(_CALIBRATION_STATE[0], ignore_errors=True)


class LimitFixture:
    """A project, machine state and Claude home, all inside one temp dir."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.state = self.base / "state"
        self.state.mkdir()
        self.claude = self.base / "claude"
        self.claude.mkdir()

    def close(self) -> None:
        self.tmp.cleanup()

    def config(self) -> None:
        write_json(self.project / ".claude" / "hybrid-hands.json", {})

    def claude_cache(self, week: str = "10.0", week_reset: float = NOW + 2 * DAY,
                     five: str = "12.3", five_reset: float = NOW + HOUR,
                     mtime: float = NOW) -> None:
        path = self.claude / ".statusline-cache.json"
        write_json(path, {
            "five": five, "five_reset": str(int(five_reset)),
            "week": week, "week_reset": str(int(week_reset)),
        })
        os.utime(path, (mtime, mtime))

    def claude_split(self, summary: Dict[str, Any]) -> None:
        write_json(self.claude / ".statusline-week-split.json", summary)

    def local_ledger(self, entries: List[tuple]) -> None:
        write_json(self.claude / ".statusline-local-usage.json", {
            "version": 4, "pricing": hashlib.sha256(
                json.dumps(load_prices(), sort_keys=True).encode()).hexdigest(), "messages": {f"m{i}": [ts, usd, "sid"] for i, (ts, usd) in enumerate(entries)}})

    def live_rate(self, pct: float, ts: float = NOW - 60,
                  reset: float = NOW + 2 * DAY, window: str = "seven_day") -> None:
        write_json(self.claude / ".hh-claude-rate-limit.json", {
            "version": 1, "updated_at": ts,
            "windows": {window: {"utilization": pct / 100.0, "ts": ts,
                                 "resets_at": reset, "status": "allowed"}},
        })

    def registry(self, run_id: str, ended: float, tokens: Dict[str, int],
                 parent: Optional[str] = None) -> None:
        write_json(self.state / "runs" / f"{run_id}.json", {
            "run_id": run_id, "label": run_id, "backend": "dsh", "model": MODEL,
            "status": "ok", "parent_session": parent, "started": iso(ended - 60),
            "ended": iso(ended), "tokens": tokens,
        })

    def session(self, session_id: str, cwd: Path) -> None:
        write_json(self.claude / "sessions" / "1.json", {
            "pid": os.getpid(), "sessionId": session_id, "cwd": str(cwd),
            "status": "busy", "name": session_id,
            "startedAt": int((NOW - 2 * HOUR) * 1000),
            "updatedAt": int((NOW - HOUR) * 1000),
        })

    def transcript(self, session_id: str, cwd: Path,
                   records: List[Dict[str, Any]], mtime: float = NOW) -> None:
        slug = str(cwd).replace("/", "-").replace(".", "-")
        path = self.claude / "projects" / slug / f"{session_id}.jsonl"
        write_text(path, "\n".join(json.dumps(record) for record in records) + "\n")
        os.utime(path, (mtime, mtime))

    @contextmanager
    def env(self, ledger_path: Optional[Path] = STATUSLINE_LEDGER) -> Iterator[None]:
        missing = self.base / "no-statusline" / "usage_ledger.py"
        saved = dict(os.environ)
        os.environ.update({
            "CLAUDE_HOME": str(self.claude),
            "CLAUDE_CONFIG_DIR": str(self.claude),
            "HYBRID_HANDS_STATE_DIR": str(self.state),
            STATUSLINE_LEDGER_ENV: str(ledger_path or missing),
        })
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def limits(self, ledger_path: Optional[Path] = STATUSLINE_LEDGER):
        with self.env(ledger_path):
            return collect_limits(self.project, NOW, env=os.environ)


def rows(limits, plan: str) -> Dict[str, object]:
    return {limit.window: limit for limit in limits if limit.plan == plan}


def simple_week(local: float = 6.2, other: float = 3.8, total: float = 10.0,
                reset: float = NOW + 2 * DAY, rate: float = 12.0,
                rate_label: str = "calib", estimated: bool = False) -> Dict[str, Any]:
    week = {"pct": total, "base": total, "reset": int(reset), "label": rate_label}
    return {
        "version": 2, "computed_at": int(NOW), "reset": int(reset),
        "window_start": int(reset - 7 * DAY), "total": total, "local": local,
        "other": other, "usd_per_pct": rate, "rate_label": rate_label,
        "claude_estimates": {"week": week} if estimated else {},
    }


class ClaudeWeekTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = LimitFixture()
        self.addCleanup(self.fx.close)

    def test_c_expired_cache_is_not_shown_as_current_and_5h_is_gone(self) -> None:
        self.fx.config()
        self.fx.claude_cache(week="6.2", week_reset=NOW - HOUR,
                             five="12.3", five_reset=NOW - 2 * HOUR)
        self.fx.claude_split(simple_week(total=6.2, reset=NOW - HOUR))
        with self.fx.env():
            week = read_claude_week(self.fx.claude, NOW)
        row = rows(self.fx.limits(), "Claude")["tuần"]
        self.assertEqual(list(rows(self.fx.limits(), "Claude")), ["tuần"])
        self.assertEqual(row.total_pct, 0.0)
        self.assertIsNone(row.resets_at)
        self.assertTrue(row.estimated)
        self.assertIsNone(week.this_machine_pct)
        self.assertIsNone(row.this_machine_pct)

    def test_c_expired_five_hour_cache_is_never_rendered(self) -> None:
        self.fx.config()
        self.fx.claude_cache(week="10.0", week_reset=NOW + 2 * DAY,
                             five="12.3", five_reset=NOW - 30 * DAY)
        self.fx.claude_split(simple_week())
        limits = self.fx.limits()
        self.assertEqual([(row.plan, row.window) for row in limits],
                         [("Claude", "tuần")])
        self.assertAlmostEqual(rows(limits, "Claude")["tuần"].total_pct, 10.0)

    def test_d_machine_and_other_come_from_the_week_split(self) -> None:
        self.fx.config()
        self.fx.claude_cache()
        self.fx.claude_split(simple_week())
        row = rows(self.fx.limits(), "Claude")["tuần"]
        self.assertAlmostEqual(row.total_pct, 10.0)
        self.assertAlmostEqual(row.this_machine_pct, 6.2)
        self.assertAlmostEqual(row.other_pct, 3.8)
        self.assertFalse(row.estimated)
        self.assertEqual(row.source, "statusline_cache+week_split")
        self.fx.claude_split(simple_week(rate=13.74, rate_label="pin"))
        self.assertFalse(rows(self.fx.limits(), "Claude")["tuần"].estimated)

    def test_e_stale_cache_extrapolates_but_expired_reset_does_not(self) -> None:
        self.fx.claude_cache(week="10.0", mtime=NOW - HOUR)
        self.fx.claude_split(simple_week(rate=13.74, rate_label="pin"))
        # Older than the cache: the live wrapper sample must not replace the cache path.
        self.fx.live_rate(15.0, ts=NOW - 2 * HOUR)
        # The on-disk ledger is frozen before the cache; fresh USD must come from the transcript.
        self.fx.local_ledger([(NOW - 2 * HOUR, 27.48)])
        self.fx.transcript("fresh", self.fx.project, [{
            "type": "assistant", "timestamp": iso(NOW - HOUR / 2),
            "cwd": str(self.fx.project), "requestId": "req",
            "message": {"id": "msg", "model": "claude-sonnet-5-5",
                        "usage": {"input_tokens": 6_870_000, "output_tokens": 0}},
        }], mtime=NOW - HOUR / 2)
        with self.fx.env():
            week = read_claude_week(self.fx.claude, NOW)
            limits = self.fx.limits()
        row = rows(limits, "Claude")["tuần"]
        self.assertFalse(week.source.startswith("rate_limit_event"))
        self.assertEqual((round(week.total_pct, 2), round(week.this_machine_pct, 2),
                          round(week.other_pct, 2)), (11.0, 7.2, 3.8))
        self.assertEqual((week.estimated, "extrapolated" in week.source), (True, True))
        self.assertEqual(round(row.total_pct, 2), 11.0)
        self.assertEqual(row.source, "statusline_cache+week_split+extrapolated")
        self.fx.claude_cache(week="6.2", week_reset=NOW - HOUR, mtime=NOW - HOUR)
        self.fx.claude_split(simple_week(total=6.2, reset=NOW - HOUR))
        with self.fx.env():
            expired = read_claude_week(self.fx.claude, NOW)
        self.assertEqual((expired.total_pct, expired.this_machine_pct), (0.0, None))
        self.assertNotIn("extrapolated", expired.source)

    def test_live_sample_newer_than_cache_is_the_total_and_skips_extrapolation(self) -> None:
        self.fx.claude_cache(week="10.0", mtime=NOW - HOUR)
        self.fx.claude_split(simple_week(rate=12.0))
        self.fx.local_ledger([(NOW - HOUR / 2, 12.0)])
        self.fx.live_rate(15.0, ts=NOW - 60)
        with self.fx.env(ledger_path=None):
            week = read_claude_week(self.fx.claude, NOW)
        row = rows(self.fx.limits(ledger_path=None), "Claude")["tuần"]
        self.assertEqual(week.total_pct, 15.0)
        self.assertFalse(week.total_estimated)
        self.assertTrue(week.split_estimated)
        self.assertAlmostEqual(week.this_machine_pct, 7.2)
        self.assertAlmostEqual(week.other_pct, 7.8)
        self.assertTrue(row.source.startswith("rate_limit_event"))
        self.assertNotIn("+extrapolated", row.source)
        # No statusline cache at all: the live sample alone still yields a week row.
        (self.fx.claude / ".statusline-cache.json").unlink()
        with self.fx.env(ledger_path=None):
            live_only = read_claude_week(self.fx.claude, NOW)
        self.assertEqual((live_only.total_pct, live_only.this_machine_pct), (15.0, 6.2))
        self.assertTrue(live_only.source.startswith("rate_limit_event"))

    def test_e_falls_back_to_the_on_disk_ledger(self) -> None:
        self.fx.claude_cache(week="10.0", mtime=NOW - HOUR)
        self.fx.claude_split(simple_week(rate=13.74, rate_label="pin"))
        self.fx.local_ledger([(NOW - HOUR / 2, 13.74)])
        with self.fx.env(ledger_path=None):
            row = rows(self.fx.limits(ledger_path=None), "Claude")["tuần"]
        self.assertEqual(round(row.total_pct, 2), 11.0)
        self.assertTrue(row.source.endswith("+extrapolated"))
        path = self.fx.claude / ".statusline-local-usage.json"
        ledger = json.loads(path.read_text())
        ledger["pricing"] = "different-prices"
        write_json(path, ledger)
        self.assertEqual(rows(self.fx.limits(ledger_path=None), "Claude")["tuần"].total_pct, 10.0)

    def test_claude_formula_matches_week_split_summary(self) -> None:
        reset = NOW + 2 * DAY
        summary = week_split.build_summary(
            [week_split.Sample(NOW, 10.0, reset)],
            {"messages": {"m": [NOW - HOUR, 74.4, "sid"]},
             "sessions": {"sid": {"cwd": str(self.fx.project)}}, "unpriced": {}},
            NOW, [], None)
        assert summary is not None
        self.fx.claude_cache()
        self.fx.claude_split(summary)
        with self.fx.env():
            week = read_claude_week(self.fx.claude, NOW)
        self.assertAlmostEqual(week.this_machine_pct, summary["local"])
        self.assertAlmostEqual(week.other_pct, summary["other"])
        self.assertAlmostEqual(week.total_pct,
                               summary["claude_estimates"]["week"]["pct"])
        self.assertAlmostEqual(week.usd_per_pct, summary["usd_per_pct"])
        self.assertAlmostEqual(
            claude_pct(74.4, week),
            summary["sessions"]["sid"]["pct"])


class RowUsageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = LimitFixture()
        self.addCleanup(self.fx.close)

    def test_snapshot_fills_week_pct_and_prices_a_legacy_dsh_run(self) -> None:
        # A historical dsh run is an ordinary hand row: canonical price, no weekly share.
        self.fx.config()
        self.fx.claude_cache()
        self.fx.claude_split(simple_week())
        self.fx.session("main", self.fx.project)
        self.fx.transcript("main", self.fx.project, [{
            "type": "assistant", "timestamp": iso(NOW - HOUR),
            "cwd": str(self.fx.project), "requestId": "req",
            "message": {"id": "msg", "model": "claude-sonnet-5-5",
                        "usage": {"input_tokens": 1_000_000, "output_tokens": 0}},
        }])
        self.fx.registry("run", NOW - HOUR, {"input": 1_000_000,
                                             "cached_input": 400_000,
                                             "output": 500_000}, "main")
        with self.fx.env():
            snapshot = build_snapshot(self.fx.project, 6 * 3600, True, now=NOW)
        session = next(s for s in snapshot.sessions if s.session_id == "main")
        self.assertAlmostEqual(session.usage.usd, 2.0)
        self.assertAlmostEqual(session.usage.week_pct, 2.0 / 12.0)
        run = session.hand_runs[0]
        data = render_json(snapshot)
        session_json = next(item for item in data["sessions"]
                            if item["session_id"] == "main")
        self.assertAlmostEqual(session_json["usage"]["week_pct"], 2.0 / 12.0)
        run_json = session_json["hand_runs"][0]["usage"]
        self.assertAlmostEqual(run_json["usd"], 0.7824, places=4)
        self.assertIsNone(run_json["week_pct"])


class ConfigAndJsonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = LimitFixture()
        self.addCleanup(self.fx.close)

    def test_json_has_weekly_limits_and_week_usage(self) -> None:
        self.fx.config()
        self.fx.claude_cache()
        self.fx.claude_split(simple_week())
        limits = self.fx.limits()
        data = render_json(Snapshot(
            sessions=[Session(
                session_id="s", name="s", status="busy", cwd="", context_tokens=None,
                started_at=NOW - HOUR, last_activity=NOW - 60, is_main=False, live=True,
                usage=Usage(read=0, cache_read=0, cache_write=0, out=0, usd=0.744,
                            week_pct=6.2, week_pct_estimated=False))],
            orphan_runs=[], since_seconds=3600, cwd="", all_projects=False,
            main_session_id=None, generated_at=NOW, limits=limits))
        self.assertEqual([row["window"] for row in data["limits"]], ["tuần"])
        self.assertEqual(set(data["limits"][0]),
                         {"plan", "window", "this_machine_pct", "other_pct",
                          "total_pct", "resets_at", "source", "estimated"})
        self.assertEqual(set(data["sessions"][0]["usage"]),
                         {"read", "cache_read", "cache_write", "out", "usd",
                          "week_pct", "week_pct_estimated", "account_plan", "account_label",
                          "account_5h_pct", "account_week_pct"})
        self.assertEqual(data["sessions"][0]["usage"]["week_pct"], 6.2)


if __name__ == "__main__":
    unittest.main()
