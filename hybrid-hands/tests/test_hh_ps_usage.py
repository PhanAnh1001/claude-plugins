"""`hh-ps` usage: dedupe/price transcripts, Go hand estimates, USD and limit-% columns."""
from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins" / "hybrid-hands" / "lib"))

from hh_ps.models import HandRun, Session, Snapshot, Subagent, Usage  # noqa: E402
from hh_ps.pricing import (  # noqa: E402
    PRICES, hand_usage, price_for, usage_usd,
)
from hh_ps.render import render_json  # noqa: E402
from hh_ps.text_render import render_text  # noqa: E402
from hh_ps.textwidth import display_width  # noqa: E402
from hh_ps.timeutil import percent_text, token_text, usd_text  # noqa: E402
from hh_ps.transcript_source import parse_transcript  # noqa: E402

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
        self.assertEqual(price_for(SONNET), PRICES["claude-sonnet-5-5"])
        self.assertEqual(price_for("claude-opus-4-20250514"), PRICES[OPUS])
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
    def test_go_backend_subtracts_cached_input_and_prices(self) -> None:
        usage = hand_usage({"input": 1_000_000, "cached_input": 400_000,
                            "output": 500_000}, "dsh")
        self.assertEqual((usage.read, usage.cache_read, usage.cache_write, usage.out),
                         (600_000, 400_000, None, 500_000))
        self.assertAlmostEqual(usage.usd, 0.7824, places=4)

    def test_go_backend_week_percent_uses_the_weekly_limit(self) -> None:
        usage = hand_usage({"input": 1_000_000, "cached_input": 400_000,
                            "output": 500_000}, "dsh", 50.0)
        self.assertAlmostEqual(usage.week_pct, 0.7824 / 50.0 * 100, places=4)
        self.assertIsNone(hand_usage({"input": 1, "output": 1}, "dsh").week_pct)

    def test_other_backend_has_tokens_but_no_usd(self) -> None:
        usage = hand_usage({"input": 1000, "cached_input": 200, "output": 10}, "codex")
        self.assertEqual(usage.read, 800)
        self.assertEqual(usage.cache_read, 200)
        self.assertIsNone(usage.usd)
        self.assertIsNone(usage.week_pct)

    def test_missing_tokens_give_no_usage(self) -> None:
        self.assertIsNone(hand_usage({}, "dsh"))


def _session(sid: str, name: str | None = None, *, live: bool = True,
             context: int | None = None, **extra) -> Session:
    return Session(session_id=sid, name=name or sid,
                   status="busy" if live else "idle", cwd="",
                   context_tokens=context, started_at=NOW - 900,
                   last_activity=NOW - 60, is_main=False, live=live, **extra)


def _tree_snapshot(sessions: list) -> Snapshot:
    return Snapshot(sessions=sessions, orphan_runs=[], since_seconds=3600, cwd="",
                    all_projects=False, main_session_id=None, generated_at=NOW)


def _main_session() -> Session:
    main = _session("main", "cha", context=157_200,
                    usage=Usage(read=1000, cache_read=2000, cache_write=300,
                                out=40, usd=0.42))
    main.is_main = True
    main.subagents.append(Subagent(
        "a1", "hybrid-hands:hand", "việc con", True, False, 2000, 60.0,
        NOW - 60, Usage(read=500, cache_read=600, cache_write=0, out=7, usd=0.02)))
    main.hand_runs.append(HandRun(
        "r1", "lượt hand", "dsh", "deepseek", "ok", "main",
        {"input": 1_000_000, "cached_input": 400_000, "output": 500_000},
        NOW - 3000, NOW - 120, 1, None, False, week_limit_usd=50.0))
    return main


def _side_session() -> Session:
    side = _session("side", "phụ:RV-12", context=800,
                    usage=Usage(read=30, cache_read=40, cache_write=0, out=5,
                                usd=0.001), ai_title="Tiêu đề tự động")
    side.parent_session = "main"
    side.side_name = "RV-12"
    side.provider = "claude"
    return side


class TextUsageTest(unittest.TestCase):
    def test_usd_and_limit_columns_align_on_two_levels(self) -> None:
        lines = render_text(_tree_snapshot([_main_session(), _side_session()])).splitlines()
        rows = [line for line in lines[2:] if "$" in line]
        self.assertEqual(len(rows), 4, "\n".join(rows))
        # USD is right-aligned: every row's USD text ends at the same cell.
        ends = {display_width(line[:line.index("$")]) + len(re.search(r"\$[\d.]+", line).group(0))
                for line in rows if "<$" not in line}
        self.assertEqual(len(ends), 1, "\n".join(rows))

    def test_side_ai_title_uses_the_hand_description_column(self) -> None:
        lines = render_text(_tree_snapshot([_main_session(), _side_session()])).splitlines()
        side = next(line for line in lines if "Tiêu đề tự động" in line)
        hand = next(line for line in lines if "lượt hand" in line)
        self.assertEqual(display_width(side[:side.index("Tiêu đề tự động")]),
                         display_width(hand[:hand.index("lượt hand")]))

    def test_rows_show_usd_and_limit_percent_but_no_tokens(self) -> None:
        text = render_text(_tree_snapshot([_main_session(), _side_session()]))
        self.assertIn("$0.42", text)
        self.assertIn("<$0.01", text)
        self.assertRegex(text, r"\$0\.78\s+1\.6% tuần")  # $0.7824 of the $50 week
        for gone in ("|", "ctx ", "out ", "1k", "500k"):
            self.assertNotIn(gone, text)

    def test_codex_side_without_numbers_prints_one_dash(self) -> None:
        side = _session("codex", "phụ:codex")
        side.parent_session, side.side_name, side.provider = "main", "codex", "codex"
        main = _session("main", "cha")
        lines = render_text(_tree_snapshot([main, side])).splitlines()
        row = next(line for line in lines if "phụ:codex" in line)
        self.assertRegex(row, r"1p\s+-$")


class JsonUsageTest(unittest.TestCase):
    def test_sessions_subagents_and_hands_carry_usage(self) -> None:
        main = _main_session()
        orphan = HandRun("r2", "hand codex", "codex", "gpt", "ok", None,
                         {"input": 90, "cached_input": 10, "output": 9},
                         NOW - 300, NOW - 100, None, None, False)
        data = render_json(Snapshot(
            sessions=[main], orphan_runs=[orphan], since_seconds=3600, cwd="",
            all_projects=False, main_session_id=None, generated_at=NOW))
        session = data["sessions"][0]
        self.assertEqual(session["usage"], {"read": 1000, "cache_read": 2000,
                                            "cache_write": 300, "out": 40,
                                            "usd": 0.42, "week_pct": None,
                                            "week_pct_estimated": False})
        self.assertEqual(session["ai_title"], "")
        agent_usage = session["subagents"][0]["usage"]
        self.assertEqual(agent_usage["out"], 7)
        hand_usage_json = session["hand_runs"][0]["usage"]
        self.assertIsNone(hand_usage_json["cache_write"])
        self.assertIsNotNone(hand_usage_json["usd"])
        self.assertAlmostEqual(hand_usage_json["week_pct"], 0.7824 / 50.0 * 100,
                               places=4)
        orphan_usage = data["orphan_runs"][0]["usage"]
        self.assertEqual(orphan_usage["read"], 80)
        self.assertIsNone(orphan_usage["usd"])
        self.assertIsNone(orphan_usage["week_pct"])

    def test_side_ai_title_is_in_json(self) -> None:
        data = render_json(_tree_snapshot([_main_session(), _side_session()]))
        side = next(item for item in data["sessions"] if item["session_id"] == "side")
        self.assertEqual(side["ai_title"], "Tiêu đề tự động")
        self.assertEqual(side["usage"]["cache_write"], 0)


class TokenFormatTest(unittest.TestCase):
    def test_compact_values_stay_stable(self) -> None:
        self.assertEqual(token_text(950), "950")
        self.assertEqual(token_text(12_000), "12k")
        self.assertEqual(token_text(1_200_000), "1.2M")


if __name__ == "__main__":
    unittest.main()
