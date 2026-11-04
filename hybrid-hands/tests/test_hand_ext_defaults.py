"""Default hand backends: DeepSeek only (dsh first, then opencode)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"))

from hand_ext.constants import DEFAULTS  # noqa: E402


class DefaultsTest(unittest.TestCase):
    def test_order_only_deepseek(self) -> None:
        self.assertEqual(DEFAULTS["order"], ["dsh", "opencode"])
        for name in ("codex", "claude", "gemini"):
            self.assertIn(name, DEFAULTS["backends"])
            self.assertNotIn(name, DEFAULTS["order"])


if __name__ == "__main__":
    unittest.main()
