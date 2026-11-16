"""day_guard_days: the v1 day guard applies only on listed local weekdays."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"))

from hand_ext import day_budget  # noqa: E402
from hand_ext.backends.claude import ClaudeMainBackend  # noqa: E402
from hand_ext.constants import DEFAULTS  # noqa: E402

SAT = datetime(2026, 11, 14, 10, 0).timestamp()
MON = datetime(2026, 11, 16, 10, 0).timestamp()
WEEKEND = {"day_guard": True, "max_day_pct": 3, "day_guard_days": ["sat", "sun"]}


def _reason(options, now, pct=None):
    """Block reason at `now`; pct None means the usage source is missing."""
    def fake_assess(opts, _now=None):
        if pct is None:
            raise day_budget.BudgetUnavailable("thiếu nguồn")
        return day_budget.DayUsage(usd=pct, usd_per_pct=1.0, pct=pct, max_pct=opts["max_day_pct"])
    real = day_budget.guard_enabled
    with patch.object(day_budget, "assess", fake_assess), \
            patch.object(day_budget, "guard_enabled", lambda o: real(o, now)):
        return ClaudeMainBackend().day_block_reason(options)


class DayGuardDaysTest(unittest.TestCase):
    def test_weekend_only(self):
        self.assertIn("3.0%", _reason(WEEKEND, SAT, pct=3.0))
        self.assertIsNone(_reason(WEEKEND, MON, pct=5.0))
        self.assertIn("không tính được", _reason(WEEKEND, SAT))
        self.assertIsNone(_reason(WEEKEND, MON))
        self.assertIn("ngoài ngày áp dụng", day_budget.inactive_reason(WEEKEND, MON))

    def test_no_days_key_guards_every_day_and_default_is_off(self):
        legacy = {"day_guard": True, "max_day_pct": 3}
        self.assertIsNotNone(_reason(legacy, MON, pct=3.0))
        self.assertIsNotNone(_reason(dict(legacy, day_guard_days=[]), MON, pct=3.0))
        self.assertIsNone(_reason(dict(DEFAULTS["claude_accounts"]["v1"]), SAT))

    def test_bad_days_is_config_error(self):
        reason = _reason(dict(WEEKEND, day_guard_days=["saturday"]), SAT, pct=0.0)
        self.assertIn("day_guard_days", reason)
        self.assertIn("day_guard_days", _reason(dict(WEEKEND, day_guard_days="sat"), SAT))


if __name__ == "__main__":
    unittest.main()
