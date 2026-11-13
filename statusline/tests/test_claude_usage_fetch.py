"""claude_usage_fetch.py with fake responses: parse every limit, keep the cache on 401/429."""
from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import claude_usage_fetch as cuf  # noqa: E402

RESPONSE = {"limits": [
    {"kind": "weekly_all", "percent": 5, "resets_at": "2026-11-20T06:00:00.44+00:00", "scope": None},
    {"kind": "weekly_scoped", "percent": 12, "resets_at": "2026-11-20T06:00:00+00:00", "is_active": True,
     "scope": {"model": {"id": "x", "display_name": "Fable"}}}],
    "extra_usage": {"is_enabled": True, "used_credits": 3.5, "currency": "USD", "email": "a@b"},
    "seven_day_opus": {"utilization": 7, "resets_at": None}, "seven_day_sonnet": None,
    "accountUuid": "secret-id"}


def fail(code: str):
    def fetch(_token: str) -> dict:
        raise cuf.FetchError(code)
    return fetch


class FetchTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def run_once(self, now: float, fetch) -> dict:
        return cuf.refresh(self.home, now, fetch=fetch, token_reader=lambda _h: "TOKEN")

    def test_parses_all_limits_numbers_only(self) -> None:
        doc = self.run_once(1000, lambda token: RESPONSE if token == "TOKEN" else {})
        self.assertEqual([(i["label"], i["percent"]) for i in doc["limits"]], [("weekly_all", 5), ("Fable", 12)])
        self.assertEqual(doc["limits"][1]["resets_at"], 1795154400)  # 2026-11-20T06:00Z
        self.assertEqual(doc["extra_usage"], {"is_enabled": True, "used_credits": 3.5, "currency": "USD"})
        self.assertEqual(doc["windows"], {"seven_day_opus": {"utilization": 7, "resets_at": None}})
        text = (self.home / cuf.CACHE_NAME).read_text()
        self.assertNotIn("TOKEN", text)
        self.assertNotIn("secret-id", text)
        self.assertEqual(stat.S_IMODE((self.home / cuf.CACHE_NAME).stat().st_mode), 0o600)

    def test_401_and_429_keep_cache_and_back_off(self) -> None:
        self.run_once(1000, lambda _t: RESPONSE)
        doc = self.run_once(1000 + cuf.REFRESH_SECONDS, fail("http 401"))
        self.assertEqual((doc["state"], doc["error"], doc["last_ok_at"]), ("error", "http 401", 1000))
        self.assertEqual(doc["limits"][1]["percent"], 12)
        later = 1000 + 2 * cuf.REFRESH_SECONDS
        doc = self.run_once(later - 1, fail("http 429"))  # still in the 300 s backoff: not retried
        self.assertEqual(doc["error"], "http 401")
        doc = self.run_once(later, fail("http 429"))
        self.assertEqual((doc["failures"], doc["next_try_at"] - doc["fetched_at"]), (2, 2 * cuf.REFRESH_SECONDS))
        self.assertEqual(json.loads((self.home / cuf.CACHE_NAME).read_text())["limits"][1]["label"], "Fable")


if __name__ == "__main__":
    unittest.main()
