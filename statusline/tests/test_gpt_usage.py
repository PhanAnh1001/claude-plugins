"""Tests for gpt_usage.py reading several Codex homes of one ChatGPT account."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import gpt_usage  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)
PRICES = {"gpt-fixture": {"input": 1_000_000, "cached": 0, "output": 0}}


def write_rollout(root: Path, name: str, thread: str, age_s: float, total: int, pct: float) -> None:
    folder = root / "sessions" / "2026"
    folder.mkdir(parents=True, exist_ok=True)
    at = (NOW - dt.timedelta(seconds=age_s)).isoformat()
    reset = (NOW + dt.timedelta(days=3)).timestamp()
    limits = {"secondary": {"used_percent": pct, "window_minutes": 10080, "resets_at": reset}}
    usage = {"input_tokens": total, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": total}
    lines = [{"type": "session_meta", "payload": {"id": thread}},
             {"type": "turn_context", "payload": {"model": "gpt-fixture"}},
             {"type": "event_msg", "timestamp": at, "payload": {
                 "type": "token_count", "rate_limits": limits, "info": {"total_token_usage": usage}}}]
    path = folder / f"rollout-{name}.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    os.utime(path, (NOW.timestamp() - age_s,) * 2)


class GptUsageDirsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.main, self.hand = self.home / ".codex", self.home / ".codex-hand"

    def test_newest_sample_wins_and_today_usd_sums_both_dirs_once_per_thread(self) -> None:
        write_rollout(self.main, "a", "t-main", 60, 1, 10.0)
        write_rollout(self.hand, "b", "t-hand", 30, 2, 71.0)
        write_rollout(self.hand, "a-copy", "t-main", 90, 1, 5.0)
        windows, usd = gpt_usage.collect([self.main, self.hand], NOW, PRICES)
        self.assertEqual(windows["7d"][0], 71.0)
        self.assertEqual(usd, "3.00")

    def test_env_single_path_overrides_and_missing_dirs_are_skipped(self) -> None:
        self.main.mkdir()
        self.hand.mkdir()
        with mock.patch.dict(os.environ, {"STATUSLINE_CODEX_DIR": str(self.hand)}):
            self.assertEqual(gpt_usage.codex_dirs(), [self.hand])
        with mock.patch.dict(os.environ, {"STATUSLINE_CODEX_DIR": ""}), \
                mock.patch.object(Path, "home", return_value=self.home):
            self.hand.rmdir()
            self.assertEqual(gpt_usage.codex_dirs(), [self.main])


if __name__ == "__main__":
    unittest.main()
