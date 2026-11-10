"""Tests for the live OpenCode Go usage fetch (go-usage-fetch.sh) and its statusline tail.

Every test uses a temporary HOME/XDG_DATA_HOME/CLAUDE_HOME, a fake auth key and a fake curl
first on PATH. Nothing here touches the real opencode.ai API or the developer's auth.json.
"""
from __future__ import annotations

import calendar
import json
import os
import re
import shutil
import stat
import tempfile
import time
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, clean_env, run_bash

STATUSLINE = SCRIPTS_DIR / "statusline.sh"
FETCH = SCRIPTS_DIR / "go-usage-fetch.sh"
FAKE_CURL = Path(__file__).resolve().parent / "fake_curl.sh"

TEST_KEY = "test-key-not-real"
CACHE_NAME = ".statusline-go-usage.json"
LOCK_NAME = ".statusline-go-usage.lock"
GO_SUMMARY = "go_usage_summary.json"
GO_STATE_ENV = "HYBRID_HANDS_STATE_DIR"
USAGE_URL = "https://opencode.ai/zen/go/v1/usage"

DIM = "\x1b[2m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

ROLLING_RESET_ISO = "2026-11-04T20:55:19.377Z"
WEEKLY_RESET_ISO = "2026-11-09T00:00:00.000Z"
MONTHLY_RESET_ISO = "2026-12-04T08:17:16.000Z"
OK_BODY = json.dumps({"usage": {
    "rolling": {"status": "ok", "percent": 0, "resetsAt": ROLLING_RESET_ISO},
    "weekly": {"status": "ok", "percent": 1, "resetsAt": WEEKLY_RESET_ISO},
    "monthly": {"status": "ok", "percent": 0, "resetsAt": MONTHLY_RESET_ISO},
}})

FIVE_PCT = 12.3
WEEK_PCT = 85
RESET_EPOCH = 1760000000
STALE_SECONDS = 900
REFRESH_SECONDS = 300
ERROR_KEEP_SECONDS = 21600


def iso_epoch(value: str) -> int:
    return calendar.timegm(time.strptime(re.sub(r"\.\d+Z$", "Z", value), "%Y-%m-%dT%H:%M:%SZ"))


def fmt_epoch(epoch: int) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(epoch))


def go_window(percent: float, resets_at: int, status: str = "ok") -> dict:
    return {"percent": percent, "status": status, "resets_at": int(resets_at)}


class GoUsageTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.claude_home = self.home / ".claude"
        self.claude_home.mkdir()
        self.xdg = self.home / "xdg"
        self.auth_file = self.xdg / "opencode" / "auth.json"
        self.cache = self.claude_home / CACHE_NAME
        self.lock = self.claude_home / LOCK_NAME
        self.workdir = self.home / "project"
        self.workdir.mkdir()
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.state_dir = self.home / "go-state"

        self.bin = self.home / "bin"
        self.bin.mkdir()
        fake_curl = self.bin / "curl"
        shutil.copyfile(FAKE_CURL, fake_curl)
        fake_curl.chmod(0o755)

        self.argv_log = self.home / "curl-argv.log"
        self.stdin_log = self.home / "curl-stdin.log"
        self.env = clean_env(
            HOME=str(self.home),
            XDG_DATA_HOME=str(self.xdg),
            CLAUDE_HOME=str(self.claude_home),
            PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            HYBRID_HANDS_STATE_DIR=str(self.state_dir),
            STATUSLINE_GO_LIVE="1",
            FAKE_CURL_LOG=str(self.argv_log),
            FAKE_CURL_STDIN_LOG=str(self.stdin_log),
        )

    # --- helpers ---

    def write_auth(self, key: str = TEST_KEY) -> None:
        self.auth_file.parent.mkdir(parents=True, exist_ok=True)
        self.auth_file.write_text(json.dumps({"opencode-go": {"type": "api", "key": key}}))

    def write_cache(self, windows: dict | None, state: str = "ok",
                    fetched_at: int | None = None, last_ok_at: int | None = None) -> None:
        document = {"fetched_at": int(time.time()) if fetched_at is None else int(fetched_at),
                    "state": state}
        if windows is not None:
            document["windows"] = windows
        if last_ok_at is not None:
            document["last_ok_at"] = int(last_ok_at)
        self.cache.write_text(json.dumps(document), encoding="utf-8")
        self.cache.chmod(0o600)

    def future_windows(self, rolling: float = 0, weekly: float = 1,
                       monthly: float = 0) -> dict:
        now = int(time.time())
        return {
            "rolling": go_window(rolling, now + 3600),
            "weekly": go_window(weekly, now + 2 * 86400),
            "monthly": go_window(monthly, now + 30 * 86400),
        }

    def write_go_summary(self, five: float, week: float) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        document = {
            "updated_at": int(time.time()),
            "models": {"deepseek-v4.1-flash": {
                "5h": {"percent": five, "estimated": True},
                "7d": {"percent": week, "estimated": True},
                "30d": {"percent": five, "estimated": True},
            }},
        }
        (self.state_dir / GO_SUMMARY).write_text(json.dumps(document), encoding="utf-8")

    def payload(self) -> str:
        return json.dumps({
            "workspace": {"current_dir": str(self.workdir)},
            "transcript_path": str(self.transcript),
            "model": {"display_name": "Opus"},
            "effort": {"level": "high"},
            "rate_limits": {
                "five_hour": {"used_percentage": FIVE_PCT, "resets_at": RESET_EPOCH},
                "seven_day": {"used_percentage": WEEK_PCT, "resets_at": RESET_EPOCH},
            },
        })

    def run_statusline(self, extra_env: dict | None = None):
        env = {**self.env, **(extra_env or {})}
        return run_bash(STATUSLINE, [], env, stdin=self.payload(), cwd=self.workdir)

    def run_fetch(self, extra_env: dict | None = None):
        return run_bash(FETCH, [], {**self.env, **(extra_env or {})})

    def go_line(self, result) -> str:
        # Go is the last row of the limit table, under the Claude/machine rows.
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.split("\n")
        self.assertGreaterEqual(len(lines), 4, result.stdout)
        claude = ANSI_ESCAPE.sub("", lines[2])
        self.assertRegex(claude, r"^Claude v1 ultra\s+5h:[^|]+ \| 7d:[^|]+$")
        return lines[3]

    def wait_for(self, predicate, timeout: float = 12.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.1)
        return predicate()

    def read_cache(self) -> dict:
        return json.loads(self.cache.read_text(encoding="utf-8"))

    def assert_cache_has_no_key(self) -> None:
        self.assertNotIn(TEST_KEY, self.cache.read_text(encoding="utf-8"))

    # --- rendering an ok cache ---

    def test_ok_cache_renders_go_on_its_own_line_and_hides_ds(self) -> None:
        now = int(time.time())
        windows = {
            "rolling": go_window(0, now + 3600),
            "weekly": go_window(1, now + 7200),
            "monthly": go_window(0, now + 86400),
        }
        self.write_cache(windows)
        self.write_go_summary(12, 31)
        line = self.go_line(self.run_statusline())
        plain = ANSI_ESCAPE.sub("", line)
        # The fresh hand-ext estimates (12/31/12) are clamped to the API integer + 0.4.
        expected = (r"^Go\s+5h:~0\.4% \(reset "
                    + re.escape(fmt_epoch(now + 3600))
                    + r"\) \| wk:~1\.4% \(reset "
                    + re.escape(fmt_epoch(now + 7200))
                    + r"\) \| mo:~0\.4% \(reset "
                    + re.escape(fmt_epoch(now + 86400)) + r"\)$")
        self.assertRegex(plain, expected)
        self.assertNotIn("DS", plain)
        self.assertIn(f"{DIM}Go{RESET}", line)
        self.assertIn(f"{GREEN}0.4%{RESET}", line)
        self.assertIn(f"{GREEN}1.4%{RESET}", line)

    def test_cache_older_than_fifteen_minutes_marks_every_window_stale(self) -> None:
        windows = self.future_windows(rolling=12, weekly=31, monthly=5)
        self.write_cache(windows, fetched_at=int(time.time()) - STALE_SECONDS - 60)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("5h:~12%", plain)
        self.assertIn("| wk:~31%", plain)
        self.assertIn("| mo:~5%", plain)

    def test_expired_reset_shows_zero_without_reset_time(self) -> None:
        now = int(time.time())
        windows = {
            "rolling": go_window(42, now - 60),
            "weekly": go_window(1, now + 7200),
            "monthly": go_window(0, now + 86400),
        }
        self.write_cache(windows)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("5h:~0%", plain)
        self.assertIn("| wk:", plain)
        self.assertNotIn("5h:~0% (reset", plain)

    def test_rate_limited_window_is_red_even_at_a_low_percent(self) -> None:
        now = int(time.time())
        windows = {
            "rolling": go_window(5, now + 3600, status="rate-limited"),
            "weekly": go_window(1, now + 7200),
            "monthly": go_window(0, now + 86400),
        }
        self.write_cache(windows)
        line = self.go_line(self.run_statusline())
        self.assertIn(f"{RED}5%{RESET}", line)
        self.assertNotIn(f"{GREEN}5%{RESET}", line)

    def test_rejected_cache_keeps_ds_with_dim_note(self) -> None:
        self.write_cache(None, state="rejected")
        self.write_go_summary(12, 31)
        line = self.go_line(self.run_statusline())
        plain = ANSI_ESCAPE.sub("", line)
        self.assertIn("DS 5h ~12.0%", plain)
        self.assertIn("tuần ~31.0%", plain)
        self.assertIn(f"{DIM}(khoá Go bị từ chối){RESET}", line)

    def test_error_cache_keeps_ds_without_note(self) -> None:
        self.write_cache(None, state="error")
        self.write_go_summary(12, 31)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("DS 5h ~12.0%", plain)
        self.assertIn("tuần ~31.0%", plain)
        self.assertNotIn("bị từ chối", plain)

    def test_error_cache_with_recent_last_ok_renders_go_stale(self) -> None:
        now = int(time.time())
        windows = self.future_windows(rolling=12, weekly=31, monthly=5)
        self.write_cache(windows, state="error", fetched_at=now - 120,
                         last_ok_at=now - 120)
        self.write_go_summary(99, 99)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("5h:~12.4%", plain)
        self.assertIn("| wk:~31.4%", plain)
        self.assertNotIn("DS", plain)

    def test_error_cache_older_than_six_hours_falls_back_to_ds(self) -> None:
        now = int(time.time())
        self.write_cache(self.future_windows(rolling=12, weekly=31),
                         state="error", fetched_at=now,
                         last_ok_at=now - ERROR_KEEP_SECONDS - 60)
        self.write_go_summary(12, 31)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("DS 5h ~12.0%", plain)
        self.assertIn("tuần ~31.0%", plain)
        self.assertNotIn("Go 5h:", plain)

    # --- background fetch from statusline ---

    def test_missing_cache_starts_background_fetch_and_returns_fast(self) -> None:
        self.write_auth()
        start = time.monotonic()
        result = self.run_statusline(extra_env={
            "FAKE_CURL_BODY": OK_BODY,
            "FAKE_CURL_HTTP_CODE": "200",
            "FAKE_CURL_SLEEP": "5",
        })
        elapsed = time.monotonic() - start
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 2.0, f"statusline waited {elapsed:.2f}s for the fetch")

        self.assertTrue(self.wait_for(lambda: self.cache.exists() and not self.lock.exists()),
                        "background fetch did not finish")
        document = self.read_cache()
        self.assertEqual(document["state"], "ok")
        self.assertEqual(stat.S_IMODE(self.cache.stat().st_mode), 0o600)
        self.assertEqual(set(document), {"fetched_at", "state", "last_ok_at", "windows"})
        self.assertEqual(set(document["windows"]), {"rolling", "weekly", "monthly"})
        expected = {
            "rolling": (0, iso_epoch(ROLLING_RESET_ISO)),
            "weekly": (1, iso_epoch(WEEKLY_RESET_ISO)),
            "monthly": (0, iso_epoch(MONTHLY_RESET_ISO)),
        }
        for name, (percent, reset) in expected.items():
            window = document["windows"][name]
            self.assertEqual(set(window), {"percent", "status", "resets_at"})
            self.assertEqual(window["percent"], percent)
            self.assertEqual(window["status"], "ok")
            self.assertEqual(window["resets_at"], reset)
        self.assert_cache_has_no_key()

    def test_curl_gets_the_key_on_stdin_not_in_argv(self) -> None:
        self.write_auth()
        result = self.run_fetch(extra_env={"FAKE_CURL_BODY": OK_BODY})
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv_log.read_text(encoding="utf-8")
        self.assertNotIn(TEST_KEY, argv)
        self.assertIn("-K", argv.splitlines())
        self.assertIn("--max-time", argv.splitlines())
        self.assertIn("15", argv.splitlines())
        self.assertIn(USAGE_URL, argv.splitlines())
        stdin = self.stdin_log.read_text(encoding="utf-8")
        self.assertIn(f"Authorization: Bearer {TEST_KEY}", stdin)

    def test_fresh_cache_does_not_start_a_fetch(self) -> None:
        self.write_auth()
        self.write_cache(self.future_windows())
        self.run_statusline()
        time.sleep(0.5)
        self.assertFalse(self.argv_log.exists())

    def test_stale_cache_starts_a_refresh(self) -> None:
        old_fetched_at = int(time.time()) - REFRESH_SECONDS - 60
        self.write_cache(self.future_windows(rolling=7), fetched_at=old_fetched_at)
        self.write_auth()
        self.run_statusline(extra_env={"FAKE_CURL_BODY": OK_BODY})
        self.assertTrue(self.wait_for(
            lambda: self.cache.exists() and self.read_cache()["fetched_at"] > old_fetched_at))
        self.assertEqual(self.read_cache()["windows"]["rolling"]["percent"], 0)
        self.assertFalse(self.lock.exists())

    def test_fresh_lock_blocks_a_second_fetch(self) -> None:
        self.write_auth()
        self.lock.mkdir()
        self.run_statusline()
        time.sleep(0.5)
        self.assertFalse(self.argv_log.exists())

    def test_go_live_zero_disables_the_network(self) -> None:
        self.write_auth()
        result = self.run_statusline(extra_env={"STATUSLINE_GO_LIVE": "0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(0.5)
        self.assertFalse(self.argv_log.exists())
        self.assertFalse(self.cache.exists())

    def test_missing_auth_key_does_not_start_a_fetch(self) -> None:
        result = self.run_statusline()
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(0.5)
        self.assertFalse(self.argv_log.exists())
        self.assertFalse(self.cache.exists())

    # --- go-usage-fetch.sh states ---

    def test_success_cache_fields_and_mode(self) -> None:
        self.write_auth()
        result = self.run_fetch(extra_env={"FAKE_CURL_BODY": OK_BODY})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(self.cache.stat().st_mode), 0o600)
        self.assertEqual(set(self.read_cache()),
                         {"fetched_at", "state", "last_ok_at", "windows"})
        self.assert_cache_has_no_key()

    def test_401_marks_rejected_without_leaking_body(self) -> None:
        self.write_auth()
        result = self.run_fetch(extra_env={
            "FAKE_CURL_BODY": '{"error":"invalid test-key-not-real"}',
            "FAKE_CURL_HTTP_CODE": "401",
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.read_cache()
        self.assertEqual(document["state"], "rejected")
        self.assertEqual(set(document), {"fetched_at", "state"})
        self.assert_cache_has_no_key()

    def test_403_marks_rejected(self) -> None:
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_HTTP_CODE": "403"})
        self.assertEqual(self.read_cache()["state"], "rejected")

    def test_500_marks_error(self) -> None:
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_HTTP_CODE": "500"})
        self.assertEqual(self.read_cache()["state"], "error")

    def test_broken_json_marks_error(self) -> None:
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_BODY": "{broken", "FAKE_CURL_HTTP_CODE": "200"})
        self.assertEqual(self.read_cache()["state"], "error")

    def test_success_sets_last_ok_at_to_fetched_at(self) -> None:
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_BODY": OK_BODY})
        document = self.read_cache()
        self.assertEqual(document["last_ok_at"], document["fetched_at"])

    def test_500_after_ok_keeps_windows_and_last_ok_at(self) -> None:
        old_fetched_at = int(time.time()) - 120
        windows = self.future_windows(rolling=12, weekly=31, monthly=5)
        self.write_cache(windows, fetched_at=old_fetched_at)
        self.write_auth()
        result = self.run_fetch(extra_env={"FAKE_CURL_HTTP_CODE": "500"})
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.read_cache()
        self.assertEqual(document["state"], "error")
        self.assertEqual(document["windows"], windows)
        self.assertEqual(document["last_ok_at"], old_fetched_at)
        self.assertGreater(document["fetched_at"], old_fetched_at)
        self.write_go_summary(99, 99)
        plain = ANSI_ESCAPE.sub("", self.go_line(self.run_statusline()))
        self.assertIn("5h:~12.4%", plain)
        self.assertNotIn("DS", plain)

    def test_broken_json_after_ok_keeps_windows(self) -> None:
        old_fetched_at = int(time.time()) - 120
        windows = self.future_windows(rolling=12, weekly=31, monthly=5)
        self.write_cache(windows, fetched_at=old_fetched_at)
        self.write_auth()
        result = self.run_fetch(extra_env={
            "FAKE_CURL_BODY": "{broken", "FAKE_CURL_HTTP_CODE": "200"})
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.read_cache()
        self.assertEqual(document["state"], "error")
        self.assertEqual(document["windows"], windows)
        self.assertEqual(document["last_ok_at"], old_fetched_at)

    def test_401_after_ok_drops_windows_and_shows_rejected_note(self) -> None:
        self.write_cache(self.future_windows(rolling=12), fetched_at=int(time.time()) - 120)
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_HTTP_CODE": "401"})
        document = self.read_cache()
        self.assertEqual(document["state"], "rejected")
        self.assertNotIn("windows", document)
        self.assertNotIn("last_ok_at", document)
        self.write_go_summary(12, 31)
        line = self.go_line(self.run_statusline())
        plain = ANSI_ESCAPE.sub("", line)
        self.assertIn("DS 5h ~12.0%", plain)
        self.assertIn("tuần ~31.0%", plain)
        self.assertIn("(khoá Go bị từ chối)", plain)
        self.assertNotIn("Go 5h:", plain)

    def test_no_key_after_ok_drops_windows(self) -> None:
        self.write_cache(self.future_windows(rolling=12), fetched_at=int(time.time()) - 120)
        self.write_auth()
        self.auth_file.unlink()
        result = self.run_fetch()
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.read_cache()
        self.assertEqual(document["state"], "no_key")
        self.assertNotIn("windows", document)
        self.assertNotIn("last_ok_at", document)

    def test_missing_auth_file_marks_no_key_without_curl(self) -> None:
        result = self.run_fetch()
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.read_cache()
        self.assertEqual(document["state"], "no_key")
        self.assertEqual(set(document), {"fetched_at", "state"})
        self.assertFalse(self.argv_log.exists())

    def test_auth_without_the_opencode_go_key_marks_no_key(self) -> None:
        self.auth_file.parent.mkdir(parents=True, exist_ok=True)
        self.auth_file.write_text(
            json.dumps({"opencode-go": {"type": "api"}}), encoding="utf-8")
        self.run_fetch()
        self.assertEqual(self.read_cache()["state"], "no_key")
        self.assertFalse(self.argv_log.exists())

    def test_fetch_leaves_only_the_cache_behind(self) -> None:
        self.write_auth()
        self.run_fetch(extra_env={"FAKE_CURL_BODY": OK_BODY})
        leftovers = sorted(
            path.name for path in self.claude_home.iterdir()
            if path.name.startswith(".statusline-go-usage"))
        self.assertEqual(leftovers, [CACHE_NAME])

    def test_stale_lock_is_replaced(self) -> None:
        self.write_auth()
        self.lock.mkdir()
        old = time.time() - 120
        os.utime(self.lock, (old, old))
        self.run_fetch(extra_env={"FAKE_CURL_BODY": OK_BODY})
        self.assertEqual(self.read_cache()["state"], "ok")
        self.assertFalse(self.lock.exists())

    def test_fetch_script_is_executable(self) -> None:
        self.assertTrue(os.access(FETCH, os.X_OK))


if __name__ == "__main__":
    unittest.main()
