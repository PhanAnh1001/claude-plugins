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
import hand_lines


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

    def test_hand_adapter_passes_cache_only_env(self):
        fake = SimpleNamespace(returncode=1, stdout='', stderr='')
        with patch.object(sys, 'argv', ['hand_lines.py', 'fake']), patch.object(hand_lines, 'executable', return_value=SCRIPTS_DIR/'fake-hh-ps'), patch.object(hand_lines.subprocess, 'run', return_value=fake) as run:
            hand_lines.main()
        self.assertEqual(run.call_args.kwargs['env']['HYBRID_HANDS_CALIBRATION_CACHE_ONLY'], '1')
        for key in ('PATH',):
            if key in os.environ:
                self.assertEqual(run.call_args.kwargs['env'][key], os.environ[key])
