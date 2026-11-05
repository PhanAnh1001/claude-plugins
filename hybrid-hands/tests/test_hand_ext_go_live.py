"""Real OpenCode Go usage: fetch script discovery, cache, live line, config and run summary."""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext import cli, go_live, isolation, render, run_cmd  # noqa: E402
from hand_ext.backends.base import RunState, Status, Usage  # noqa: E402
from hand_ext.config import load_config  # noqa: E402
from hand_ext.runner import RunOutcome  # noqa: E402

NOW = 1_700_000_000
MODEL = "deepseek-v4.1-flash"
PRICE = {"input": 1.0, "cached_input": 0.1, "output": 2.0}
STATE_ENV = "HYBRID_HANDS_STATE_DIR"
HOME_ENV = "CLAUDE_HOME"
FETCH_ENV = "HYBRID_HANDS_GO_FETCH"
LIVE_ENV = "HYBRID_HANDS_GO_LIVE"
TOKENS = {"input": 1000, "cached_input": 400, "output": 100}


def _windows(start: float = NOW) -> dict:
    return {
        "rolling": {"percent": 16, "status": "ok", "resets_at": start + 3600},
        "weekly": {"percent": 8, "status": "ok", "resets_at": start + 2 * 86400},
        "monthly": {"percent": 4, "status": "ok", "resets_at": start + 21 * 86400},
    }


def _cache(path: Path, *, state: str = "ok", fetched_at: float = NOW,
           last_ok_at: float | None = None, windows: dict | None = None,
           with_windows: bool = True) -> dict:
    doc = {"fetched_at": fetched_at, "state": state}
    if last_ok_at is not None:
        doc["last_ok_at"] = last_ok_at
    if with_windows:
        doc["windows"] = _windows() if windows is None else windows
    path.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def _write_manifest(home: Path, plugins: dict) -> None:
    path = home / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")


def _install_script(base: Path, name: str) -> Path:
    script = base / name / "scripts" / "go-usage-fetch.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    return script


class CliHomeTest(unittest.TestCase):
    def test_claude_home_precedence(self) -> None:
        self.assertEqual(go_live.claude_home({"CLAUDE_HOME": "/a",
                                              "CLAUDE_CONFIG_DIR": "/b"}), Path("/a"))
        self.assertEqual(go_live.claude_home({"CLAUDE_CONFIG_DIR": "/b"}), Path("/b"))

    def test_claude_home_defaults_to_dot_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"HOME": tmp}):
                self.assertEqual(go_live.claude_home({}), Path(tmp) / ".claude")

    def test_cache_path(self) -> None:
        self.assertEqual(go_live.cache_path(Path("/h")),
                         Path("/h") / ".statusline-go-usage.json")


class FindFetchScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "claude"
        self.home.mkdir()

    def test_env_override_wins(self) -> None:
        override = _install_script(self.base, "custom")
        _write_manifest(self.home, {"statusline@statusline-local": [
            {"installPath": str(self.base / "installed"), "version": "1"}]})
        self.assertEqual(go_live.find_fetch_script({FETCH_ENV: str(override)}, self.home),
                         override)

    def test_env_override_missing_means_no_script(self) -> None:
        self.assertIsNone(go_live.find_fetch_script(
            {FETCH_ENV: str(self.base / "absent.sh")}, self.home))

    def test_standard_plugin_key(self) -> None:
        installed = _install_script(self.base, "installed")
        _write_manifest(self.home, {
            "other@local": [{"installPath": str(self.base / "other"), "version": "1"}],
            "statusline@statusline-local": [
                {"installPath": str(installed.parents[1]), "version": "1"}],
        })
        self.assertEqual(go_live.find_fetch_script({}, self.home), installed)

    def test_any_statusline_key_is_fallback(self) -> None:
        installed = _install_script(self.base, "installed")
        _write_manifest(self.home, {
            "other@local": [{"installPath": str(self.base / "other"), "version": "1"}],
            "statusline@another": [
                {"installPath": str(installed.parents[1]), "version": "1"}],
        })
        self.assertEqual(go_live.find_fetch_script({}, self.home), installed)

    def test_no_manifest_or_missing_script(self) -> None:
        self.assertIsNone(go_live.find_fetch_script({}, self.home))
        _write_manifest(self.home, {"statusline@statusline-local": [
            {"installPath": str(self.base / "absent"), "version": "1"}]})
        self.assertIsNone(go_live.find_fetch_script({}, self.home))

    def test_corrupt_manifest(self) -> None:
        path = self.home / "plugins" / "installed_plugins.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(go_live.find_fetch_script({}, self.home))


class FetchTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "claude"
        self.home.mkdir()
        self.script = self.base / "fetch.sh"
        self.script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        self.cache = go_live.cache_path(self.home)

    def test_argv_env_and_devnull(self) -> None:
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0)

        go_live.fetch(self.script, self.home, run_fn=runner, now_fn=lambda: NOW,
                      sleep_fn=lambda _: self.fail("không được chờ khi chưa có cache"))
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertEqual(argv, ["bash", str(self.script)])
        self.assertEqual(kwargs["env"][HOME_ENV], str(self.home))
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 20)

    def test_timeout_is_swallowed(self) -> None:
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 20)

        go_live.fetch(self.script, self.home, run_fn=runner, now_fn=lambda: NOW,
                      sleep_fn=lambda _: self.fail("không được chờ khi chưa có cache"))

    def test_waits_for_cache_from_concurrent_fetch(self) -> None:
        _cache(self.cache, fetched_at=NOW - 10)
        clock = [float(NOW)]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
            if len(sleeps) == 3:
                _cache(self.cache, fetched_at=clock[0])

        go_live.fetch(self.script, self.home,
                      run_fn=lambda argv, **kw: subprocess.CompletedProcess(argv, 0),
                      now_fn=lambda: clock[0], sleep_fn=sleep)
        self.assertEqual(sleeps, [0.5, 0.5, 0.5])
        self.assertGreaterEqual(json.loads(self.cache.read_text())["fetched_at"], NOW)

    def test_wait_is_bounded(self) -> None:
        _cache(self.cache, fetched_at=NOW - 10)
        clock = [float(NOW)]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        go_live.fetch(self.script, self.home,
                      run_fn=lambda argv, **kw: subprocess.CompletedProcess(argv, 0),
                      now_fn=lambda: clock[0], sleep_fn=sleep)
        self.assertEqual(len(sleeps), 20)  # wait_s / 0.5, no unbounded loop


class ReadLiveTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / ".statusline-go-usage.json"

    def test_fresh_ok(self) -> None:
        _cache(self.path, fetched_at=NOW - 30)
        live = go_live.read_live(self.path, NOW)
        self.assertTrue(live["fresh"])
        self.assertEqual(live["age_s"], 30)
        self.assertEqual(live["windows"]["5h"], {"percent": 16, "resets_at": NOW + 3600})
        self.assertEqual(live["windows"]["tuần"]["percent"], 8)
        self.assertEqual(live["windows"]["tháng"]["percent"], 4)

    def test_ok_at_freshness_boundary_is_stale(self) -> None:
        _cache(self.path, fetched_at=NOW - 120)
        live = go_live.read_live(self.path, NOW)
        self.assertFalse(live["fresh"])
        self.assertEqual(live["age_s"], 120)

    def test_error_keeps_old_windows_with_last_ok_age(self) -> None:
        _cache(self.path, state="error", fetched_at=NOW - 10, last_ok_at=NOW - 720)
        live = go_live.read_live(self.path, NOW)
        self.assertFalse(live["fresh"])
        self.assertEqual(live["age_s"], 720)
        self.assertEqual(live["windows"]["5h"]["percent"], 16)

    def test_error_without_windows_or_last_ok_is_none(self) -> None:
        _cache(self.path, state="error", fetched_at=NOW - 10, with_windows=False)
        self.assertIsNone(go_live.read_live(self.path, NOW))
        _cache(self.path, state="error", fetched_at=NOW - 10, last_ok_at=None,
               windows={"rolling": {"percent": 1, "resets_at": NOW}})
        self.assertIsNone(go_live.read_live(self.path, NOW))

    def test_rejected_no_key_missing_and_corrupt(self) -> None:
        for state in ("rejected", "no_key"):
            _cache(self.path, state=state, with_windows=False)
            self.assertIsNone(go_live.read_live(self.path, NOW))
        self.path.unlink()
        self.assertIsNone(go_live.read_live(self.path, NOW))
        self.path.write_text("{broken", encoding="utf-8")
        self.assertIsNone(go_live.read_live(self.path, NOW))

    def test_incomplete_or_non_numeric_windows_are_none(self) -> None:
        windows = _windows()
        del windows["monthly"]
        _cache(self.path, windows=windows)
        self.assertIsNone(go_live.read_live(self.path, NOW))
        windows = _windows()
        windows["rolling"]["percent"] = "16"
        _cache(self.path, windows=windows)
        self.assertIsNone(go_live.read_live(self.path, NOW))

    def test_ok_without_fetched_at_is_none(self) -> None:
        self.path.write_text(json.dumps({"state": "ok", "windows": _windows()}),
                             encoding="utf-8")
        self.assertIsNone(go_live.read_live(self.path, NOW))


class LiveLineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()

    def tearDown(self) -> None:
        if self.original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.original_tz
        time.tzset()

    def live(self, fresh: bool, age_s: int = 0) -> dict:
        return {"fresh": fresh, "age_s": age_s,
                "windows": {"5h": {"percent": 16, "resets_at": NOW + 3600},
                            "tuần": {"percent": 8, "resets_at": NOW + 2 * 86400},
                            "tháng": {"percent": 4, "resets_at": NOW + 21 * 86400}}}

    def test_fresh_line_formats_reset_times(self) -> None:
        self.assertEqual(
            go_live.live_line(self.live(True), NOW),
            "hạn mức Go (thật): 16% 5h (reset 23:13), 8% tuần (reset 16/11 22:13), "
            "4% tháng (reset 05/12 22:13)")

    def test_stale_line_marks_every_number_and_age(self) -> None:
        self.assertEqual(
            go_live.live_line(self.live(False, 12 * 60), NOW),
            "hạn mức Go (thật): ~16% 5h (reset 23:13), ~8% tuần (reset 16/11 22:13), "
            "~4% tháng (reset 05/12 22:13) (cache 12 phút trước)")


class RefreshAndReadTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "claude"
        self.home.mkdir()
        self.cache = go_live.cache_path(self.home)

    def test_disabled_by_config_does_not_call_fetch(self) -> None:
        env = {HOME_ENV: str(self.home)}
        self.assertIsNone(go_live.refresh_and_read(
            False, env, run_fn=lambda *a, **k: self.fail("không được fetch")))
        self.assertFalse(self.cache.exists())

    def test_disabled_by_env_does_not_call_fetch(self) -> None:
        env = {HOME_ENV: str(self.home), LIVE_ENV: "0"}
        self.assertIsNone(go_live.refresh_and_read(
            True, env, run_fn=lambda *a, **k: self.fail("không được fetch")))

    def test_without_script_reads_existing_cache(self) -> None:
        _cache(self.cache, fetched_at=NOW)
        live = go_live.refresh_and_read(
            True, {HOME_ENV: str(self.home)}, run_fn=lambda *a, **k: self.fail("không fetch"),
            now_fn=lambda: NOW)
        self.assertTrue(live["fresh"])

    def test_fetch_then_read(self) -> None:
        script = self.base / "fetch.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        def runner(argv, **kwargs):
            _cache(self.cache, fetched_at=NOW)
            return subprocess.CompletedProcess(argv, 0)

        live = go_live.refresh_and_read(
            True, {HOME_ENV: str(self.home), FETCH_ENV: str(script)},
            run_fn=runner, now_fn=lambda: NOW)
        self.assertTrue(live["fresh"])

    def test_any_exception_returns_none(self) -> None:
        script = self.base / "fetch.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        def boom():
            raise RuntimeError("boom")

        self.assertIsNone(go_live.refresh_and_read(
            True, {HOME_ENV: str(self.home), FETCH_ENV: str(script)},
            run_fn=lambda *a, **k: subprocess.CompletedProcess([], 0), now_fn=boom))


class LiveConfigTest(unittest.TestCase):
    def project(self, base: Path, go_section: dict) -> Path:
        project = base / "project"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"ext_hand": {"go_usage": go_section}}), encoding="utf-8")
        return project

    def test_default_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(self.project(Path(tmp), {}))
        self.assertIs(cfg.go_usage_live, True)

    def test_false_is_honoured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(self.project(Path(tmp), {"live": False}))
        self.assertIs(cfg.go_usage_live, False)

    def test_wrong_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                load_config(self.project(Path(tmp), {"live": "yes"}))
        self.assertIn("go_usage.live", str(caught.exception))


class _GoCfg:
    def __init__(self, base: Path) -> None:
        self.go_usage_ledger = base / "go_usage.jsonl"
        self.go_usage_summary = base / "go_usage_summary.json"
        self.go_monthly_limit_usd = 100.0
        self.go_usage_live = True

    def options(self, name: str) -> dict:
        return {"go_price_per_mtok": PRICE} if name == "dsh" else {}


class RunSummaryLiveTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "claude"
        self.home.mkdir()
        self.cfg = _GoCfg(self.base)
        self.entry = {"run_id": "run-1", "ended": time.strftime(
            "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()), "backend": "dsh",
            "model": MODEL, "status": "ok", "tokens": dict(TOKENS), "cwd": str(self.base)}
        self.outcome = RunOutcome(Status.OK, 0, RunState(usage=Usage(1000, 400, 100)),
                                  1.0, [])
        env = {HOME_ENV: str(self.home), FETCH_ENV: "", LIVE_ENV: "1"}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_real_line_plus_secondary_estimate(self) -> None:
        _cache(go_live.cache_path(self.home), fetched_at=time.time())
        go_line, extra = run_cmd._record_go(self.cfg, self.entry, self.outcome)
        self.assertTrue(go_line.startswith("hạn mức Go (thật): "), go_line)
        self.assertEqual(len(extra), 1)
        self.assertTrue(extra[0].startswith("ước tính từ sổ: "), extra)
        self.assertIn("5h", extra[0])
        text = render.run_summary(self.entry, 1.0, None, "", [], go_line=go_line,
                                  extra_lines=extra)
        self.assertIn(go_line, text)
        self.assertIn(extra[0], text)

    def test_without_cache_keeps_estimated_line(self) -> None:
        go_line, extra = run_cmd._record_go(self.cfg, self.entry, self.outcome)
        self.assertTrue(go_line.startswith("hạn mức: ~"), go_line)
        self.assertTrue(go_line.endswith("(ước tính)"), go_line)
        self.assertEqual(extra, [])

    def test_config_live_false_ignores_cache(self) -> None:
        _cache(go_live.cache_path(self.home), fetched_at=time.time())
        self.cfg.go_usage_live = False
        go_line, extra = run_cmd._record_go(self.cfg, self.entry, self.outcome)
        self.assertTrue(go_line.startswith("hạn mức: ~"), go_line)
        self.assertEqual(extra, [])


class _BucketBackend:
    name = "dsh"


class AttemptSummaryLiveTest(unittest.TestCase):
    """`_attempt` prints the real line first and the ledger estimate as a secondary line."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.project = self.base / "project"
        (self.project / ".claude").mkdir(parents=True)
        (self.project / ".claude" / "hybrid-hands.json").write_text(json.dumps(
            {"ext_hand": {
                "order": ["dsh"], "isolation": "none", "runs_dir": "runs",
                "ledger": "ledger.json", "quota_state": "quota.json",
                "go_usage": {"ledger": "go_usage.jsonl", "monthly_limit_usd": 100},
                "backends": {"dsh": {"model": MODEL, "go_price_per_mtok": PRICE}},
            }}), encoding="utf-8")
        self.home = self.base / "claude"
        self.home.mkdir()
        env = {HOME_ENV: str(self.home), FETCH_ENV: "", LIVE_ENV: "1",
               STATE_ENV: str(self.base / "state")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cfg = load_config(self.project)
        self.args = argparse.Namespace(model=None, effort=None, sandbox=None,
                                       timeout_min=None, max_tokens=None, browser=False,
                                       no_apply=True, keep_worktree=True)
        self.outcome = RunOutcome(Status.OK, 0, RunState(usage=Usage(1000, 400, 100)),
                                  1.0, [])

    def attempt(self) -> str:
        ctx = isolation.IsolationContext(mode=isolation.ISOLATION_NONE,
                                         source_root=self.project, run_cwd=self.project)
        out = io.StringIO()
        with mock.patch.object(run_cmd, "run_backend", return_value=self.outcome), \
                mock.patch.object(run_cmd.isolation, "prepare", return_value=ctx), \
                mock.patch.object(run_cmd.isolation, "finalize",
                                  return_value=isolation.ApplyResult()), \
                mock.patch.object(run_cmd.isolation, "cleanup", return_value=""), \
                mock.patch.object(run_cmd.isolation, "append_report"), \
                mock.patch.object(run_cmd.isolation, "summary_line",
                                  return_value="isolation: none"), \
                redirect_stdout(out):
            code = run_cmd._attempt(self.cfg, self.args, _BucketBackend(), "prompt", "lab",
                                    self.project,
                                    isolation.IsolationChoice(isolation.ISOLATION_NONE))
        self.assertEqual(code, 0, out.getvalue())
        return out.getvalue()

    def test_run_summary_prefers_real_numbers(self) -> None:
        _cache(go_live.cache_path(self.home), fetched_at=time.time())
        out = self.attempt()
        self.assertIn("hạn mức Go (thật): 16% 5h", out)
        self.assertIn("ước tính từ sổ: ~0% 5h", out)

    def test_run_summary_keeps_old_line_without_cache(self) -> None:
        out = self.attempt()
        self.assertIn("hạn mức: ~0% 5h, ~0% tuần (ước tính)", out)
        self.assertNotIn("ước tính từ sổ:", out)


class UsageCliLiveTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.project = self.base / "project"
        (self.project / ".claude").mkdir(parents=True)
        (self.project / ".claude" / "hybrid-hands.json").write_text(json.dumps(
            {"ext_hand": {"order": [], "go_usage": {"monthly_limit_usd": 100}}}),
            encoding="utf-8")
        self.state = self.base / "state"
        self.state.mkdir()
        self.home = self.base / "claude"
        self.home.mkdir()
        self.cache = go_live.cache_path(self.home)
        env = {STATE_ENV: str(self.state), HOME_ENV: str(self.home),
               FETCH_ENV: "", LIVE_ENV: "1"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.project)])
        return code, out.getvalue()

    def test_usage_text_and_json_include_live(self) -> None:
        _cache(self.cache, fetched_at=time.time())
        code, out = self.cli("usage", "--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual(data["live"]["windows"]["5h"]["percent"], 16)
        code, out = self.cli("usage")
        self.assertEqual(code, 0, out)
        self.assertIn("hạn mức Go (thật): 16% 5h", out)

    def test_usage_without_cache_says_unavailable(self) -> None:
        code, out = self.cli("usage", "--json")
        self.assertEqual(code, 0, out)
        self.assertIsNone(json.loads(out)["live"])
        code, out = self.cli("usage")
        self.assertEqual(code, 0, out)
        self.assertIn("hạn mức Go (thật): chưa lấy được", out)

    def test_status_reads_cache_without_fetching(self) -> None:
        _cache(self.cache, fetched_at=time.time())
        marker = self.base / "fetched"
        fake = self.base / "fetch.sh"
        fake.write_text(f"#!/bin/bash\ntouch {marker}\n", encoding="utf-8")
        os.environ[FETCH_ENV] = str(fake)
        code, out = self.cli("status")
        self.assertEqual(code, 0, out)
        self.assertIn("hạn mức Go (thật): 16% 5h", out)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
