"""Unit tests: pricing, rollout meter, ledger locking, setup merge."""
import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"
sys.path.insert(0, str(LIB))

from hand_gpt import ledger  # noqa: E402
from hand_gpt.constants import DEFAULT_PRICES  # noqa: E402
from hand_gpt.pricing import Tokens, cost_for_call, cost_usd  # noqa: E402
from hand_gpt.rollout import RolloutMeter  # noqa: E402
from hand_gpt.setup_doctor import merge_top_level  # noqa: E402

WRITERS = 2
ENTRIES_PER_WRITER = 25


def _writer(path: str, who: int) -> None:
    for i in range(ENTRIES_PER_WRITER):
        ledger.append_entry(Path(path), {"run_id": f"{who}-{i}", "usd": 0.01})


class PricingTest(unittest.TestCase):
    def test_normal_price(self):
        t = Tokens(input=1_000_000, cached_input=200_000, output=100_000)
        # 800K*1.0 + 200K*0.05 + 100K*5.0 = 0.8 + 0.01 + 0.5
        self.assertAlmostEqual(cost_usd(t, DEFAULT_PRICES), 1.31)

    def test_long_prompt_price(self):
        t = Tokens(input=300_000, cached_input=100_000, output=10_000)
        # 200K*2.0 + 100K*0.1 + 10K*7.5 = 0.4 + 0.01 + 0.075
        self.assertAlmostEqual(cost_for_call(t, DEFAULT_PRICES), 0.485)

    def test_threshold_boundary_is_normal(self):
        t = Tokens(input=272_000)
        self.assertAlmostEqual(cost_for_call(t, DEFAULT_PRICES), 0.272)


class RolloutTest(unittest.TestCase):
    def test_meter_prices_deltas_and_skips_partial_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.jsonl"
            step = {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 0}
            two = {k: v * 2 for k, v in step.items()}
            ev = lambda tot: json.dumps({"type": "event_msg", "payload": {
                "type": "token_count", "info": {"total_token_usage": tot, "last_token_usage": step}}})
            p.write_text(ev(step) + "\n" + ev(two) + "\n" + '{"partial')
            m = RolloutMeter(DEFAULT_PRICES)
            m.attach(p)
            self.assertAlmostEqual(m.poll(), 200 / 1e6)
            self.assertEqual(m.total.input, 200)
            self.assertEqual(m.events, 2)


class LedgerTest(unittest.TestCase):
    def test_concurrent_writers_lose_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "sub/usage.json")
            procs = [multiprocessing.Process(target=_writer, args=(path, w)) for w in range(WRITERS)]
            for p in procs:
                p.start()
            for p in procs:
                p.join(60)
            entries = ledger.read_entries(Path(path))
            self.assertEqual(len(entries), WRITERS * ENTRIES_PER_WRITER)
            self.assertEqual(len({e["run_id"] for e in entries}), WRITERS * ENTRIES_PER_WRITER)


class MergeTopLevelTest(unittest.TestCase):
    KEYS = {"model": "gpt-6.1-sol", "service_tier": "flex"}

    def test_sets_keys_keeps_user_keys_drops_legacy(self):
        text = ('model = "old"\nuser_key = 1\n\n[profiles.hand]\nmodel = "x"\n\n'
                '[mcp_servers.a]\ncommand = "y"\n')
        out = merge_top_level(text, self.KEYS)
        self.assertIn('model = "gpt-6.1-sol"\n', out)
        self.assertIn('service_tier = "flex"\n', out)
        self.assertIn("user_key = 1", out)
        self.assertNotIn("[profiles.hand]", out)
        self.assertIn('[mcp_servers.a]\ncommand = "y"', out)
        self.assertLess(out.index("service_tier"), out.index("[mcp_servers.a]"))
        self.assertEqual(merge_top_level(out, self.KEYS), out)

    def test_empty_file(self):
        out = merge_top_level("", self.KEYS)
        self.assertEqual(out, 'model = "gpt-6.1-sol"\nservice_tier = "flex"\n')


if __name__ == "__main__":
    unittest.main()
