"""side_session codex specifics: optional -p, rollout filtered by session start."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from side_session import constants as C, tokens  # noqa: E402
from side_session.commands import provider_argv  # noqa: E402

OLD_AGE_S = 3600  # an earlier hand-gpt run finished an hour before the session


class CodexArgvTest(unittest.TestCase):
    def _cfg(self, profile: str) -> SimpleNamespace:
        return SimpleNamespace(codex_profile=profile, codex_home=Path("/h"), claude_args=[])

    def test_default_profile_is_empty(self):
        self.assertEqual(C.DEFAULTS["codex_profile"], "")

    def test_no_p_flag_when_profile_empty(self):
        argv, env = provider_argv(self._cfg(""), C.PROVIDER_CODEX, "n", "u", "/w", "hi")
        self.assertNotIn("-p", argv)
        self.assertEqual(env["CODEX_HOME"], "/h")

    def test_p_flag_when_profile_set(self):
        argv, _ = provider_argv(self._cfg("x"), C.PROVIDER_CODEX, "n", "u", "/w", "hi")
        self.assertEqual(argv[1:3], ["-p", "x"])


class RolloutSinceTest(unittest.TestCase):
    def test_older_rollout_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            day = Path(d) / C.CODEX_SESSIONS_SUBDIR / "2026/11/04"
            day.mkdir(parents=True)
            old = day / "rollout-2026-11-04T00-00-00-old.jsonl"
            old.write_text("{}\n")
            past = time.time() - OLD_AGE_S
            os.utime(old, (past, past))
            started = time.time() - 1
            self.assertIsNone(tokens.codex_rollout(Path(d), "nomatch", started))
            new = day / "rollout-2026-11-04T01-00-00-new.jsonl"
            new.write_text("{}\n")
            self.assertEqual(tokens.codex_rollout(Path(d), "nomatch", started), new)
            self.assertEqual(tokens.codex_rollout(Path(d), "old"), old)


if __name__ == "__main__":
    unittest.main()
