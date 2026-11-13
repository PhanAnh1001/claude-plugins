"""Tests for scripts/usage_ledger.py: USD prices, dedupe, session ids and the incremental scan."""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from _support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
import usage_ledger as ul  # noqa: E402

OPUS = "claude-opus-5-5"
HAIKU = "claude-haiku-5-5"
FABLE = "claude-fable-5-2"  # id written by transcripts for Claude Fable 5.2
MILLION = 1_000_000


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def record(msg_id: str, epoch: float, model: str = OPUS, usage: dict | None = None,
           cwd: str = "/repo", request_id: str | None = None) -> str:
    return json.dumps({
        "type": "assistant", "requestId": request_id or f"req-{msg_id}", "timestamp": iso(epoch),
        "cwd": cwd, "message": {"id": msg_id, "model": model,
                                "usage": usage or {"output_tokens": MILLION}},
    })


class PriceTest(unittest.TestCase):
    def test_opus_and_haiku_prices(self) -> None:
        usage = {"input_tokens": MILLION, "output_tokens": MILLION}
        self.assertAlmostEqual(ul.usage_usd(ul.price_for(OPUS), usage), 24.0)
        self.assertAlmostEqual(ul.usage_usd(ul.price_for(HAIKU), usage), 0.60)
        self.assertAlmostEqual(ul.usage_usd(ul.price_for(FABLE), usage), 48.0)
        self.assertAlmostEqual(ul.usage_usd(ul.price_for("claude-sonnet-5-5"), usage), 12.0)

    def test_stale_cache_does_not_hide_marketplace_prices(self) -> None:
        import shared_prices as sp
        with tempfile.TemporaryDirectory() as tmp:
            home, live = Path(tmp) / "claude", Path(tmp) / "live"
            stale = home / "plugins/cache/m/hybrid-hands/0.55.0"
            for root, models in ((stale, {OPUS: 1}), (live / sp.PLUGIN_SUBDIR, {OPUS: 9, FABLE: 8})):
                (root / "config").mkdir(parents=True)
                (root / sp.PRICES_RELATIVE).write_text(json.dumps({"version": 1, "models": {
                    m: {"input": v, "cached": 0, "output": v} for m, v in models.items()}}))
            (home / "plugins/known_marketplaces.json").write_text(
                json.dumps({"m": {"source": {"source": "directory", "path": str(live)}}}))
            with patch.dict("os.environ", {"CLAUDE_HOME": str(home)}), \
                    patch.object(sp, "__file__", str(Path(tmp) / "a/b/c/d/x.py")):
                rows = sp.load_prices()
        self.assertEqual((rows[OPUS]["input"], rows[FABLE]["input"]), (9, 8))

    def test_unknown_model_is_unpriced(self) -> None:
        self.assertIsNone(ul.price_for("claude-opus-9-1"))
        self.assertIsNone(ul.price_for("claude-haiku-4-5"))
        self.assertIsNone(ul.price_for("gpt-x"))

    def test_cache_kinds(self) -> None:
        price = ul.price_for(OPUS)  # input 4 USD/MTok
        split = {"cache_creation_input_tokens": 2 * MILLION, "cache_read_input_tokens": MILLION,
                 "cache_creation": {"ephemeral_1h_input_tokens": MILLION,
                                    "ephemeral_5m_input_tokens": MILLION}}
        self.assertAlmostEqual(ul.usage_usd(price, split), 4 * (2 + 1.25 + 0.05))
        lump = {"cache_creation_input_tokens": MILLION}
        self.assertAlmostEqual(ul.usage_usd(price, lump), 4 * 1.25)

    def test_synthetic_skipped_and_unpriced_flagged(self) -> None:
        now = time.time()
        self.assertIsNone(ul.usage_record(record("a", now, model="<synthetic>").encode(), "s"))
        rec = ul.usage_record(record("b", now, model="gpt-x").encode(), "s")
        self.assertEqual((rec.usd, rec.priced), (0.0, False))

    def test_missing_both_ids_skipped(self) -> None:
        line = json.dumps({"type": "assistant", "timestamp": iso(time.time()),
                           "message": {"model": OPUS, "usage": {"output_tokens": 1}}})
        self.assertIsNone(ul.usage_record(line.encode(), "s"))

    def test_session_id_from_path(self) -> None:
        self.assertEqual(ul.session_id_for(Path("/p/proj/abc.jsonl")), "abc")
        self.assertEqual(ul.session_id_for(Path("/p/proj/abc/subagents/agent-1.jsonl")), "abc")


class LedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        (self.home / "projects" / "p" / "s1" / "subagents").mkdir(parents=True)
        self.main = self.home / "projects" / "p" / "s1.jsonl"
        self.sub = self.home / "projects" / "p" / "s1" / "subagents" / "agent-1.jsonl"
        self.now = time.time()

    def write(self, path: Path, lines: list[str], mode: str = "w") -> None:
        with path.open(mode, encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def ledger(self) -> dict:
        return ul.update_ledger(self.home, self.now)

    def total(self, ledger: dict) -> float:
        return sum(m[1] for m in ledger["messages"].values())

    def test_last_record_wins(self) -> None:
        self.write(self.main, [record("m", self.now - 10, usage={"output_tokens": 1}),
                               record("m", self.now - 5)])
        ledger = self.ledger()
        self.assertEqual(len(ledger["messages"]), 1)
        self.assertAlmostEqual(self.total(ledger), 20.0)

    def test_subagent_counts_for_parent_session(self) -> None:
        self.write(self.main, [record("a", self.now - 10)])
        self.write(self.sub, [record("b", self.now - 10, model=HAIKU, cwd="/repo/sub")])
        ledger = self.ledger()
        self.assertEqual({m[2] for m in ledger["messages"].values()}, {"s1"})
        self.assertEqual(ledger["sessions"]["s1"]["cwd"], "/repo/sub")

    def test_incremental_scan(self) -> None:
        self.write(self.main, [record("a", self.now - 10)])
        self.ledger()
        offset = ul.load_ledger(self.home / ul.LEDGER_NAME)["files"][str(self.main)]["offset"]
        self.assertEqual(offset, self.main.stat().st_size)
        self.write(self.main, [record("b", self.now - 5)], mode="a")
        self.assertAlmostEqual(self.total(self.ledger()), 40.0)
        self.assertAlmostEqual(self.total(self.ledger()), 40.0)
        rows = ul.load_prices()
        rows[OPUS] = {**rows[OPUS], "output": 30}
        with patch.object(ul, "load_prices", return_value=rows):
            self.assertAlmostEqual(self.total(self.ledger()), 60.0)
        ul.refresh_prices()

    def test_partial_last_line_waits(self) -> None:
        self.main.write_text(record("a", self.now - 10), encoding="utf-8")
        self.assertEqual(self.ledger()["messages"], {})

    def test_v1_ledger_rescanned_and_old_data_pruned(self) -> None:
        (self.home / ul.LEDGER_NAME).write_text(json.dumps(
            {"version": 1, "files": {str(self.main): {"ino": 0, "offset": 999}}}))
        old = self.now - ul.RETENTION_SECONDS - 100
        self.write(self.main, [record("old", old), record("new", self.now - 10)])
        ledger = self.ledger()
        self.assertEqual(ledger["version"], ul.LEDGER_VERSION)
        self.assertEqual(list(ledger["messages"]), ["new|req-new"])

    def test_opus_and_fable_mix_priced_per_model(self) -> None:
        self.write(self.main, [record("a", self.now - 10), record("b", self.now - 5, model=FABLE)])
        ledger = self.ledger()
        self.assertAlmostEqual(self.total(ledger), 60.0)  # 20 Opus + 40 Fable, feeds machine %
        self.assertEqual(ledger["unpriced"], {})

    def test_unpriced_models_listed(self) -> None:
        self.write(self.main, [record("a", self.now - 10, model="gpt-x")])
        self.assertEqual(list(self.ledger()["unpriced"]), ["gpt-x"])


class WindowReportTest(unittest.TestCase):
    def test_window_dedupes_and_drops_after_until(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, now = Path(tmp), time.time()
            sub = home / "projects" / "-repo" / "s1" / "subagents"
            sub.mkdir(parents=True)
            (home / "projects" / "-repo" / "s1.jsonl").write_text("\n".join([
                record("a", now - 50), record("a", now - 50),  # one message, two lines
                record("old", now - 500), record("late", now + 50)]) + "\n")
            (sub / "agent-x.jsonl").write_text(record("b", now - 10) + "\n")
            found = ul.window_messages([home], now - 100, now)
            self.assertEqual(sorted(k.split("|")[0] for k in found), ["a", "b"])
            self.assertIn("subagent_usd\t20.00", ul.window_report(found))


if __name__ == "__main__":
    unittest.main()
