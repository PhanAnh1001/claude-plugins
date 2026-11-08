"""Native child metadata, using isolated fake homes only."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "plugins/hybrid-hands/lib"))
sys.path.insert(0, str(TESTS / "fixtures/hh_ps"))
from fixture import HhFixture, MAIN_SESSION, NOW, iso
from hh_ps.tree import build_snapshot
from hh_ps.render import render_json, render_text


class NativeTest(unittest.TestCase):
    def fixture(self, tokens=True):
        fx = HhFixture()
        self.addCleanup(fx.close)
        root = fx.home / ".codex-hand/sessions"
        root.mkdir(parents=True)
        pinned = root / "rollout-parent.jsonl"
        pinned.write_text(json.dumps({"type": "session_meta", "payload": {"id": "sol-thread"}}) + "\n")
        for child, event in (("done", "task_complete"), ("failed", "task_failed"),
                             ("cancelled", "task_cancelled"), ("unknown", None)):
            records = [{"type": "session_meta", "payload": {"id": child, "description": "Sửa sidebar và panel",
                "source": {"subagent": {"thread_spawn": {"parent_thread_id": "sol-thread"}}},
                "timestamp": iso(NOW - 100)}},
                {"type": "turn_context", "payload": {"model": "gpt-6.1-sol", "effort": "low"}},
                {"type": "response_item", "payload": {"text": "CHAT_SENTINEL"}}]
            if event:
                records += [{"timestamp": iso(NOW - 90), "type": "event_msg", "payload": {"type": "task_started"}},
                            {"timestamp": iso(NOW - 10), "type": "event_msg", "payload": {"type": event, "last_agent_message": "DO_NOT_RETAIN"}}]
            if tokens:
                records.append({"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 100, "output_tokens": 10}}}})
            if child == "unknown":
                records[1:1] = [
                    {"type": "session_meta", "payload": {"id": "sol-thread", "model": "ancestor-model", "timestamp": iso(NOW - 200)}},
                    {"timestamp": iso(NOW - 110), "type": "event_msg", "payload": {"type": "task_complete", "exit_code": 3}}]
            (root / ("rollout-" + child + ".jsonl")).write_text("\n".join(map(json.dumps, records)) + "\n")
        return fx, pinned

    def test_alias_json_status_and_hand_exit(self):
        fx, pinned = self.fixture()
        fx._run("nonzero", backend="codex", parent_session=MAIN_SESSION,
                status="ok", exit=3, started=iso(NOW - 20), ended=iso(NOW - 10))
        with fx.env(), mock.patch("hh_ps.tree.pinned_rollouts", return_value={MAIN_SESSION: str(pinned)}):
            snapshot = build_snapshot(fx.project, 3600, False, now=NOW)
        session = next(s for s in render_json(snapshot)["sessions"] if s["session_id"] == MAIN_SESSION)
        self.assertTrue(all(a["exit_code"] is None for a in session["subagents"]
                            if a["agent_type"] != "native-codex"))
        children = {a["agent_id"]: a for a in session["subagents"] if a["agent_type"] == "native-codex"}
        self.assertEqual(children["done"]["status"], "completed")
        self.assertEqual(children["done"]["description"], "Sửa sidebar và panel")
        self.assertEqual(children["done"]["parent_session"], MAIN_SESSION)
        self.assertEqual((children["done"]["model"], children["done"]["effort"], children["done"]["provider"]), ("gpt-6.1-sol", "low", "codex"))
        self.assertEqual(children["failed"]["status"], "failed")
        self.assertEqual(children["cancelled"]["status"], "cancelled")
        self.assertEqual(children["unknown"]["status"], "unknown")
        self.assertEqual((children["unknown"]["parent_session"], children["unknown"]["model"]), (MAIN_SESSION, ""))
        self.assertIsNone(children["unknown"]["usage"]["usd"])
        self.assertIsNone(children["unknown"]["duration_seconds"])
        self.assertEqual(next(r for r in session["hand_runs"] if r["run_id"] == "nonzero")["exit_code"], 3)
        self.assertIn("✗", render_text(snapshot))
        self.assertNotIn("DO_NOT_RETAIN", json.dumps(session))
        # One machine thread, duplicated rollout, pre-window baseline and a reset.
        from types import SimpleNamespace
        from hh_ps.machine_usage import machine_usage
        from hh_ps.codex import GptWindow
        from hand_ext.codex_usage import price_for
        from hand_ext.go_usage import estimate_cost
        machine_home = fx.home / "machine"
        machine_root = machine_home / "sessions"
        machine_root.mkdir(parents=True)
        start = NOW - 1000
        records = [{"type": "session_meta", "payload": {"id": "unique-machine-thread",
                    "timestamp": iso(start - 100), "model": "gpt-6.1-sol"}}]
        for stamp, count in ((start - 10, 100), (start + 10, 150),
                             (start + 20, 150), (start + 30, 20)):
            records.append({"type": "event_msg", "timestamp": iso(stamp),
                "payload": {"type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": count, "cached_input_tokens": 0, "output_tokens": count}}}})
        text = "\n".join(map(json.dumps, records)) + "\n"
        for name in ("one", "duplicate"):
            (machine_root / f"rollout-{name}.jsonl").write_text(text)
        source = SimpleNamespace(home=machine_home, account={"tuần": GptWindow(
            10, start + 7 * 86400, NOW, "fixture")})
        totals = machine_usage(fx.claude, None, source, None, NOW)
        expected = estimate_cost({"input": 70, "cached_input": 0, "output": 70},
                                 price_for({}, "gpt-6.1-sol"))
        self.assertAlmostEqual(totals[1]["usd"], expected)
        self.assertIsNone(totals[0]["usd"])
        archive = machine_home / "archived_sessions"
        archive.mkdir()
        (archive / "rollout-duplicate.jsonl").write_text(text)
        self.assertAlmostEqual(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"], expected)
        unique = archive / "rollout-unique.jsonl"
        unique_text = text.replace("unique-machine-thread", "archived-unique")
        unique.write_text(unique_text)
        self.assertAlmostEqual(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"], 2 * expected)
        unique.chmod(0)
        self.assertIsNone(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"])
        unique.chmod(0o600)
        # A cached delta above its input delta is incomplete/incoherent coverage.
        bad = json.loads(json.dumps(records))
        bad[2]["payload"]["info"]["total_token_usage"]["cached_input_tokens"] = 100
        unique.write_text("\n".join(map(json.dumps, bad)).replace("unique-machine-thread", "archived-unique"))
        self.assertIsNone(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"])
        bad[2]["payload"]["info"]["total_token_usage"]["cached_input_tokens"] = 0
        bad[-1]["payload"]["info"]["total_token_usage"]["output_tokens"] = 200
        unique.write_text("\n".join(map(json.dumps, bad)).replace("unique-machine-thread", "archived-unique"))
        self.assertIsNone(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"])
        unique.write_text(unique_text)
        for path in machine_root.glob("*.jsonl"):
            path.write_text(text.replace("gpt-6.1-sol", "unknown-model"))
        self.assertIsNone(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"])
        source.account = {}
        self.assertIsNone(machine_usage(fx.claude, None, source, None, NOW)[1]["usd"])


    def test_absent_native_tokens_remain_unknown(self):
        fx, pinned = self.fixture(tokens=False)
        with fx.env(), mock.patch("hh_ps.tree.pinned_rollouts", return_value={MAIN_SESSION: str(pinned)}):
            snapshot = build_snapshot(fx.project, 3600, False, now=NOW)
        children = [a for s in snapshot.sessions for a in s.subagents if a.provider == "codex"]
        self.assertEqual(len(children), 4)
        self.assertTrue(all(a.usage.usd is None for a in children))
        self.assertTrue(all(a.usage.account_plan == "GPT" for a in children))
        self.assertIn("~$?", render_text(snapshot))
        totals = render_json(snapshot)["machine_usage"]
        self.assertIsNone(next(row for row in totals if row["plan"] == "GPT")["usd"])


    def test_unpinned_main_discovery_is_repo_scoped(self):
        fx, pinned = self.fixture(tokens=False)
        records = [{"type": "session_meta", "payload": {"id": "sol-thread",
            "cwd": str(fx.project), "title": "Sol chính", "timestamp": iso(NOW - 100), "source": "cli"}},
            {"timestamp": iso(NOW - 90), "type": "event_msg", "payload": {"type": "task_started"}}]
        pinned.write_text("\n".join(map(json.dumps, records)) + "\n")
        other = dict(records[0], payload=dict(records[0]["payload"], id="other-repo", cwd=str(fx.home / "other")))
        (pinned.parent / "rollout-other.jsonl").write_text(json.dumps(other) + "\n")
        with fx.env(), mock.patch("hh_ps.tree.pinned_rollouts", return_value={}):
            snapshot = build_snapshot(fx.project, 3600, False, now=NOW)
        parents = {s.session_id: s for s in snapshot.sessions}
        self.assertNotIn("other-repo", parents)
        parent = parents["sol-thread"]
        self.assertEqual((parent.provider, parent.status, parent.model), ("codex", "running", ""))
        self.assertEqual({a.agent_id for a in parent.subagents}, {"done", "failed", "cancelled", "unknown"})
        self.assertEqual(parent.name, "Sol chính")
        self.assertIsNone(parent.usage.usd)
        self.assertEqual(sum(s.session_id == "sol-thread" for s in snapshot.sessions), 1)
