"""`hh-ps`: live Claude sessions, subagents, external hand runs and the text/JSON trees."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PLUGIN_LIB = TESTS.parent / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
sys.path.insert(0, str(TESTS / "fixtures" / "hh_ps"))

from fixture import (  # noqa: E402
    HhFixture, MAIN_SESSION, OLD_SESSION, SIDE_SESSION, SECRET_KEY, SECRET_PROMPT,
    SECRET_SOCKET,
)
from hh_ps import cli  # noqa: E402
from hh_ps.timeutil import parse_since  # noqa: E402

ARGPARSE_EXIT = 2


class HhPsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = HhFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str) -> tuple:
        out = io.StringIO()
        with self.fx.env(), redirect_stdout(out):
            code = cli.main(list(args) + ["--cwd", str(self.fx.project)])
        return code, out.getvalue()

    def json_cli(self, *args: str) -> dict:
        code, out = self.run_cli("--json", *args)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_live_sessions_ended_and_since_filter(self) -> None:
        code, out = self.run_cli("--ended")
        self.assertEqual(code, 0, out)
        self.assertIn("WP-23b", out)
        self.assertNotIn("live-main", out)  # customTitle beats the session-file name
        self.assertIn("▶ WP-23b", out)  # ▶ marks this (main) session
        self.assertIn("ended-name", out)
        self.assertIn("○ ended-name", out)
        self.assertIn("○ đã dừng", out)  # legend line
        self.assertIn("sess-non", out)  # first 8 characters of the id
        self.assertNotIn("old-name", out)
        self.assertNotIn(OLD_SESSION, out)
        self.assertNotIn("sess-other", out)

    def test_all_includes_other_project(self) -> None:
        code, out = self.run_cli("--all", "--ended")
        self.assertEqual(code, 0, out)
        self.assertIn("sess-oth", out)

    def test_subagent_states(self) -> None:
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        self.assertIn("▶ hand", out)
        self.assertIn("✓ hand", out)
        self.assertIn("im lặng", out)
        self.assertNotIn("  xong", out)  # ok children print no status word
        self.assertNotIn("việc cũ đã xong", out)  # finished outside --since
        self.assertIn("việc đang chạy …", out)

    def test_hand_runs_parent_grouping_orphans_and_lost(self) -> None:
        data = self.json_cli()
        sessions = {item["session_id"]: item for item in data["sessions"]}
        main_runs = {run["run_id"]: run for run in sessions[MAIN_SESSION]["hand_runs"]}
        self.assertEqual(main_runs["main-run"]["state"], "running")
        self.assertEqual(main_runs["lost-run"]["state"], "lost")
        self.assertEqual([run["run_id"] for run in sessions[SIDE_SESSION]["hand_runs"]],
                         ["side-run"])
        self.assertEqual([run["run_id"] for run in data["orphan_runs"]],
                         ["orphan-run"])
        self.assertNotIn("old-run", json.dumps(data))
        _, out = self.run_cli()
        self.assertIn("mất", out)
        self.assertNotIn("tiến trình đã chết", out)
        self.assertNotIn("cached", out)
        self.assertIn("hand ngoài không rõ phiên gọi", out)

    def test_token_caps_and_ratios_from_meta_and_side_state(self) -> None:
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        # Text shows context only; caps and ratios stay in --json.
        self.assertIn("ctx 6k", out)
        self.assertIn("ctx 12k", out)
        self.assertNotIn("/200k", out)
        data = self.json_cli()
        caps = {item["session_id"]: item["token_cap"] for item in data["sessions"]}
        self.assertEqual(caps[MAIN_SESSION], 200000)
        self.assertEqual(caps[SIDE_SESSION], 50000)

    def test_json_schema(self) -> None:
        data = self.json_cli()
        self.assertEqual(data["schema"], 1)
        self.assertTrue(data["generated_at"])
        self.assertEqual(data["since_seconds"], 6 * 3600)
        self.assertEqual(data["main_session_id"], MAIN_SESSION)
        self.assertFalse(data["all_projects"])
        self.assertEqual(data["totals"], {"live_sessions": 2,
                                          "running_subagents": 1,
                                          "running_hand_runs": 1})
        session = {item["session_id"]: item for item in data["sessions"]}[MAIN_SESSION]
        self.assertEqual(session["name"], "WP-23b")
        self.assertTrue(session["is_main"])
        self.assertEqual(session["status"], "busy")
        self.assertEqual(session["context_tokens"], 6000)
        self.assertEqual(session["token_cap"], 200000)
        self.assertAlmostEqual(session["token_ratio"], 0.03, places=4)
        self.assertEqual(session["subagents"][0]["status"], "running")
        self.assertEqual(set(session["subagents"][0]),
                         {"agent_id", "agent_type", "description", "status",
                          "context_tokens", "usage", "duration_seconds", "ended_at"})
        run = session["hand_runs"][0]
        self.assertEqual(set(run), {"run_id", "label", "backend", "model", "status",
                                    "state", "tokens", "usage", "started_at", "ended_at",
                                    "duration_seconds", "parent_session", "pid",
                                    "child_pid"})
        self.assertEqual(set(session["usage"]),
                         {"read", "cache_read", "cache_write", "out", "usd"})
        self.assertIn("ai_title", session)
        self.assertEqual(set(run["tokens"]), {"input", "cached_input", "output"})
        self.assertEqual(len(data["orphan_runs"]), 1)

    def test_main_session_flag_overrides_env(self) -> None:
        data = self.json_cli("--main-session", SIDE_SESSION)
        self.assertEqual(data["main_session_id"], SIDE_SESSION)
        sessions = {item["session_id"]: item for item in data["sessions"]}
        self.assertTrue(sessions[SIDE_SESSION]["is_main"])
        self.assertFalse(sessions[MAIN_SESSION]["is_main"])
        self.assertEqual([session_id for session_id, item in sessions.items() if item["is_main"]],
                         [SIDE_SESSION])

    def test_main_session_rejects_non_uuid(self) -> None:
        stderr = io.StringIO()
        with self.fx.env(), redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                cli.main(["--main-session", "not-a-uuid", "--cwd", str(self.fx.project)])
        self.assertEqual(raised.exception.code, ARGPARSE_EXIT)
        self.assertIn("UUID", stderr.getvalue())

    def test_no_secret_key_prompt_or_socket_is_read_or_printed(self) -> None:
        self.assertEqual(self.fx.key_path.stat().st_mode & 0o777, 0)
        code, out = self.run_cli("--all")
        self.assertEqual(code, 0, out)
        self.assertNotIn(SECRET_KEY, out)
        self.assertNotIn(SECRET_PROMPT, out)
        self.assertNotIn(SECRET_SOCKET, out)
        self.assertNotIn("messagingSocketPath", out)

    def test_stdout_not_tty_has_no_ansi_colour(self) -> None:
        _, out = self.run_cli()
        self.assertNotIn("\x1b[", out)

    def test_watch_requires_at_least_two_seconds(self) -> None:
        with self.fx.env(), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cli.main(["--watch", "1", "--cwd", str(self.fx.project)])
        self.assertEqual(raised.exception.code, ARGPARSE_EXIT)

    def test_watch_one_iteration_returns(self) -> None:
        code, out = self.run_cli("--watch", "2", "--count", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("Tổng:", out)

    def test_since_parser(self) -> None:
        self.assertEqual(parse_since("6h"), 6 * 3600)
        self.assertEqual(parse_since("90m"), 90 * 60)
        self.assertEqual(parse_since("2d"), 2 * 86400)
        for bad in ("", "6", "h", "1.5h", "-2h", "6w"):
            with self.assertRaises(ValueError):
                parse_since(bad)


if __name__ == "__main__":
    unittest.main()
