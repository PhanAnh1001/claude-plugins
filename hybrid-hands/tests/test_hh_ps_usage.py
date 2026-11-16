"""Shared usage library: dedupe/price transcripts, hand token usage, USD and limit-% columns."""
from __future__ import annotations

__import__("os").environ["HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"] = "1"  # never read real account files
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))

from hh_ps.pricing import (  # noqa: E402
    PRICES, hand_usage, price_for, usage_usd,
)
from hh_ps.timeutil import percent_text, token_text, usd_text  # noqa: E402
from hh_ps.transcript_source import parse_transcript  # noqa: E402
from unittest.mock import patch  # noqa: E402


def isolate_store(case: unittest.TestCase, state: Path) -> None:
    """Point plugin state at a temp dir so tests never touch the real state."""
    env = patch.dict("os.environ", {"HYBRID_HANDS_STATE_DIR": str(state)})
    env.start()
    case.addCleanup(env.stop)

NOW = 1_800_000_000.0
OPUS = "claude-opus-5-5"
SONNET = "sonnet-4-20250514"  # family fallback, not an exact PRICES key
HAIKU = "claude-haiku-5-5"


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def usage_line(message_id: str, request_id: str, model: str, *, input_tokens: int = 0,
               cached: int = 0, created: int = 0, output: int = 0,
               created_detail: dict | None = None) -> str:
    usage: dict = {
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cached,
        "cache_creation_input_tokens": created,
        "output_tokens": output,
    }
    if created_detail is not None:
        usage["cache_creation"] = created_detail
    return json.dumps({
        "type": "assistant",
        "timestamp": iso(NOW - 60),
        "requestId": request_id,
        "message": {"id": message_id, "model": model, "usage": usage},
    })


def title_line(kind: str, key: str, value: str) -> str:
    return json.dumps({"type": kind, key: value})


class TranscriptUsageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "session.jsonl"
        isolate_store(self, Path(self.tmp.name) / "state")

    def _parse(self, lines: list) -> object:
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return parse_transcript(self.path)

    def test_dedupe_message_id_and_keep_last_record(self) -> None:
        info = self._parse([
            usage_line("m1", "r1", OPUS, input_tokens=1000, cached=200,
                       created=300, output=50),
            usage_line("m1", "r1", OPUS, input_tokens=1000, cached=200,
                       created=300, output=50),
            usage_line("m2", "r2", OPUS, input_tokens=10, output=1),
            usage_line("m2", "r2", OPUS, input_tokens=20, output=2),
        ])
        self.assertEqual(info.usage.read, 1020)
        self.assertEqual(info.usage.cache_read, 200)
        self.assertEqual(info.usage.cache_write, 300)
        self.assertEqual(info.usage.out, 52)

    def test_same_message_id_with_other_request_id_counts(self) -> None:
        info = self._parse([
            usage_line("m1", "r1", OPUS, input_tokens=100),
            usage_line("m1", "r2", OPUS, input_tokens=1),
        ])
        self.assertEqual(info.usage.read, 101)

    def test_ai_title_last_record_wins(self) -> None:
        info = self._parse([
            title_line("custom-title", "customTitle", "Tên cũ"),
            title_line("ai-title", "aiTitle", "Tiêu đề một"),
            title_line("ai-title", "aiTitle", "Tiêu đề hai"),
        ])
        self.assertEqual(info.custom_title, "Tên cũ")
        self.assertEqual(info.ai_title, "Tiêu đề hai")

    def test_synthetic_model_is_not_priced_or_counted(self) -> None:
        info = self._parse([
            usage_line("s1", "r1", "<synthetic>", input_tokens=500, output=5),
        ])
        self.assertIsNone(info.usage)

    def test_cache_creation_detail_splits_the_token_count(self) -> None:
        info = self._parse([
            usage_line("m1", "r1", SONNET, created_detail={
                "ephemeral_1h_input_tokens": 100,
                "ephemeral_5m_input_tokens": 200,
            }),
        ])
        self.assertEqual(info.usage.cache_write, 300)

    def test_usd_uses_each_message_model(self) -> None:
        info = self._parse([
            usage_line("m1", "r1", OPUS, input_tokens=1_000_000),
            usage_line("m2", "r2", "claude-sonnet-5-5", input_tokens=1_000_000),
        ])
        self.assertAlmostEqual(info.usage.usd, 6.0)  # Opus 4 + Sonnet 2


class ClaudePriceTest(unittest.TestCase):
    def test_opus_sonnet_haiku_and_family_fallback(self) -> None:
        self.assertEqual(price_for(OPUS), PRICES[OPUS])
        self.assertEqual(price_for(HAIKU), PRICES[HAIKU])
        self.assertIsNone(price_for(SONNET))
        self.assertIsNone(price_for("claude-opus-4-20250514"))
        self.assertIsNone(price_for("unknown-model"))

    def test_cache_write_5m_and_1h_prices(self) -> None:
        sonnet = price_for("claude-sonnet-5-5")
        five_minutes = {"cache_creation_input_tokens": 1_000_000}
        one_hour = {"cache_creation": {"ephemeral_1h_input_tokens": 1_000_000}}
        self.assertAlmostEqual(usage_usd(sonnet, five_minutes), 2.5)
        self.assertAlmostEqual(usage_usd(sonnet, one_hour), 4.0)

    def test_usd_text(self) -> None:
        self.assertEqual(usd_text(0.42), "$0.42")
        self.assertEqual(usd_text(0.009), "<$0.01")
        self.assertIsNone(usd_text(None))
        self.assertEqual(usd_text(0.0), "$0")

    def test_percent_text_has_one_decimal(self) -> None:
        self.assertEqual(percent_text(12.34), "12.3%")
        self.assertEqual(percent_text(12.0), "12.0%")
        self.assertEqual(percent_text(0.0), "0.0%")
        self.assertEqual(percent_text(0.01), "<0.1%")
        self.assertIsNone(percent_text(None))


class HandUsageTest(unittest.TestCase):
    def test_hand_tokens_split_cached_input_and_leave_usd_to_enrichment(self) -> None:
        usage = hand_usage({"input": 1000, "cached_input": 200, "output": 10})
        self.assertEqual((usage.read, usage.cache_read, usage.cache_write, usage.out),
                         (800, 200, None, 10))
        self.assertIsNone(usage.usd)
        self.assertIsNone(usage.week_pct)
        self.assertIsNone(hand_usage({}))



class TokenFormatTest(unittest.TestCase):
    def test_compact_values_stay_stable(self) -> None:
        self.assertEqual(token_text(950), "950")
        self.assertEqual(token_text(12_000), "12k")
        self.assertEqual(token_text(1_200_000), "1.2M")


if __name__ == "__main__":
    unittest.main()
