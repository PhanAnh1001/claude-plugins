"""Shared calibration integration; fixtures only, no account calls."""
import os
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from _support import SCRIPTS_DIR
sys.path.insert(0, str(SCRIPTS_DIR))
import week_split as ws
import shared_usage


class CalibrationIntegrationTests(unittest.TestCase):
    def test_pin_shared_legacy_precedence(self):
        samples = [ws.Sample(1000, 10, 10000)]
        ledger = dict(messages={}, sessions={}, unpriced={})
        with patch.object(shared_usage, 'claude_calibration', return_value={'usd_per_pct':3}):
            self.assertEqual(ws.build_summary(samples, ledger, 1100, pin=5)['usd_per_pct'], 5)
            self.assertEqual(ws.build_summary(samples, ledger, 1100)['usd_per_pct'], 3)
        with patch.object(shared_usage, 'claude_calibration', return_value={}):
            self.assertEqual(ws.build_summary(samples, ledger, 1100)['usd_per_pct'], ws.PRIOR_USD_PER_PCT)

    def test_shared_reader_only_uses_cached(self):
        fake = SimpleNamespace(cached=lambda now: {'usd_per_pct':7})
        with patch.object(shared_usage, 'shared_module', return_value=fake):
            self.assertEqual(shared_usage.claude_calibration(1100)['usd_per_pct'], 7)
