"""`cc-switch`: move one Claude Code session between the terminal TUI and Paseo."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Optional

TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent / "plugins" / "hybrid-hands"
BIN = PLUGIN / "bin" / "cc-switch"
sys.path.insert(0, str(TESTS / "fixtures" / "cc_switch"))

from cc_fixture import (  # noqa: E402
    AGENT_A, AGENT_ARCHIVED, AGENT_B, AGENT_ORPHAN, AGENT_OTHER, AGENT_P,
    AGENT_SOLO, AGENT_TUI, IMPORTED_AGENT, MODEL, SECRET_CONFIG, SECRET_KEY,
    SECRET_NATIVE, SECRET_PROMPT, SECRET_SOCKET, SID_A, SID_IMPORT, SID_NO_USER,
    SID_ORPHAN, SID_OTHER, SID_P, SID_SOLO, SID_TUI, TITLE_A, TITLE_IMPORT,
    CcFixture, slugify,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
EXIT_PASEO = 5
TIMEOUT = 30


class CcSwitchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = CcFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str, cwd: Optional[Path] = None,
                **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BIN), *args],
            cwd=str(cwd or self.fx.project), env=self.fx.env(**env),
            capture_output=True, text=True, timeout=TIMEOUT,
        )

    def calls(self, command: str) -> list:
        return [call for call in self.fx.calls() if call["cmd"] == command]

    def handoff_path(self) -> Path:
        return self.fx.state / "cc-switch" / "handoff.json"

    def seed_handoff(self, session_id: str, agent_id: str = AGENT_A) -> None:
        path = self.handoff_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            str(self.fx.project.resolve()): {
                "session_id": session_id, "agent_id": agent_id,
                "at": int(time.time()),
            },
        }), encoding="utf-8")

    def handoff_entries(self) -> dict:
        if not self.handoff_path().exists():
            return {}
        return json.loads(self.handoff_path().read_text(encoding="utf-8"))

    # ---- term ----------------------------------------------------------
    def test_term_single_agent_execs_claude_in_agent_cwd(self) -> None:
        result = self.run_cli("term", cwd=self.fx.solo)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        claude = self.calls("claude")
        self.assertEqual(len(claude), 1)
        self.assertEqual(claude[0]["argv"], ["--resume", SID_SOLO, "--model", MODEL])
        self.assertEqual(Path(claude[0]["cwd"]).resolve(), self.fx.solo.resolve())
        self.assertIn("Đang dùng ở terminal", result.stdout)

    def test_term_multiple_agents_exits_two_with_list(self) -> None:
        result = self.run_cli("term")
        self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
        for agent_id in (AGENT_A, AGENT_B, AGENT_P, AGENT_TUI):
            self.assertIn(agent_id[:8], result.stdout)
        self.assertIn("--agent", result.stdout)
        self.assertEqual(self.calls("claude"), [])

    def test_term_no_agent_exits_three_with_hint(self) -> None:
        result = self.run_cli("term", cwd=self.fx.empty)
        self.assertEqual(result.returncode, EXIT_NOT_FOUND, result.stderr)
        self.assertIn("gợi ý", result.stderr.lower())
        self.assertEqual(self.calls("claude"), [])

    def test_term_running_agent_waits_before_exec(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_B)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        calls = self.fx.calls()
        commands = [call["cmd"] for call in calls]
        self.assertIn("wait", [call["argv"][0] for call in calls
                               if call["cmd"] == "paseo"])
        wait_index = next(index for index, call in enumerate(calls)
                          if call["cmd"] == "paseo" and call["argv"][:1] == ["wait"])
        claude_index = commands.index("claude")
        self.assertLess(wait_index, claude_index)
        wait_args = calls[wait_index]["argv"]
        self.assertEqual(wait_args, ["wait", AGENT_B])
        self.assertIn("đang chờ agent rảnh", result.stdout)

    def test_term_live_tui_same_session_exits_four_without_exec(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_TUI)
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stderr)
        self.assertIn(str(self.fx.tui_pid), result.stderr)
        self.assertIn("/exit", result.stderr)
        self.assertEqual(self.calls("claude"), [])

    def test_term_agent_prefix(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_A[:8])
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.calls("claude")[0]["argv"][:2], ["--resume", SID_A])

    def test_term_forwards_args_after_double_dash(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_A, "--", "--verbose", "x")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.calls("claude")[0]["argv"],
                         ["--resume", SID_A, "--model", MODEL, "--verbose", "x"])

    def test_term_dry_run_prints_only_command(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_A, "--dry-run")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         f"claude --resume {SID_A} --model {MODEL}")
        self.assertEqual(self.fx.calls(), [])

    def test_term_writes_handoff_ledger_for_current_project(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_A)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        entry = self.handoff_entries()[str(self.fx.project.resolve())]
        self.assertEqual(entry["session_id"], SID_A)
        self.assertEqual(entry["agent_id"], AGENT_A)
        self.assertIsInstance(entry["at"], (int, float))
        self.assertEqual(len(self.calls("claude")), 1)

    def test_term_dry_run_does_not_write_handoff_ledger(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_A, "--dry-run")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertFalse(self.handoff_path().exists())

    def test_term_ledger_write_error_warns_but_still_execs_claude(self) -> None:
        blocker = self.fx.base / "blocked-state"
        blocker.write_text("not a directory", encoding="utf-8")
        result = self.run_cli("term", "--agent", AGENT_A,
                              HYBRID_HANDS_STATE_DIR=str(blocker))
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn("sổ bàn giao", result.stderr)
        self.assertEqual(len(self.calls("claude")), 1)

    def test_term_waits_when_paseo_ls_reports_running_over_last_status(self) -> None:
        result = self.run_cli(
            "term", "--agent", AGENT_A,
            PASEO_FAKE_LS_STDOUT=self.fx.ls_json({AGENT_A: "running"}),
        )
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        paseo_calls = [call["argv"] for call in self.calls("paseo")]
        self.assertIn(["ls", "--json"], paseo_calls)
        self.assertIn(["wait", AGENT_A], paseo_calls)
        self.assertLess(paseo_calls.index(["ls", "--json"]),
                        paseo_calls.index(["wait", AGENT_A]))
        self.assertIn("đang chờ agent rảnh", result.stdout)

    def test_term_falls_back_to_last_status_when_paseo_ls_fails(self) -> None:
        result = self.run_cli("term", "--agent", AGENT_B, PASEO_FAKE_LS_EXIT="1")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        paseo_calls = [call["argv"] for call in self.calls("paseo")]
        self.assertIn(["wait", AGENT_B], paseo_calls)

    # ---- paseo ---------------------------------------------------------
    def test_paseo_v2_provider_dry_run_and_import(self) -> None:
        account = self.fx.home / ".claude-hand"
        self.fx.claude.rename(account)
        global_config = self.fx.home / "global.json"
        global_config.write_text(json.dumps({"paseo": {"claude_providers": {"v2": "wrong"}}}))
        repo_config = self.fx.project / ".claude" / "hybrid-hands.json"
        repo_config.parent.mkdir()
        repo_config.write_text(json.dumps({"paseo": {"claude_providers": {"v2": "claude-hand"}}}))
        env = {"CLAUDE_CONFIG_DIR": str(account), "HYBRID_HANDS_CONFIG": str(global_config)}
        dry = self.run_cli("paseo", "--session", SID_IMPORT, "--dry-run", **env)
        self.assertEqual(dry.returncode, EXIT_OK, dry.stderr)
        self.assertIn("--provider claude-hand", dry.stdout)
        self.assertEqual(self.fx.calls(), [])
        result = self.run_cli("paseo", "--session", SID_IMPORT, **env)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        argv = self.calls("paseo")[0]["argv"]
        self.assertEqual(argv[:4], ["import", SID_IMPORT, "--provider", "claude-hand"])
        self.assertEqual(Path(argv[5]).resolve(), self.fx.project.resolve())
        mismatch = self.run_cli("paseo", "--session", SID_A, **env)
        self.assertNotEqual(mismatch.returncode, EXIT_OK)
        self.assertEqual(len(self.fx.calls()), 1)
    def test_paseo_v2_missing_provider_blocks_import(self) -> None:
        for extra in ((), ("--dry-run",)):
            result = self.run_cli("paseo", "--session", SID_IMPORT, *extra,
                                  CLAUDE_CONFIG_DIR=str(self.fx.home / ".claude-hand"))
            self.assertNotEqual(result.returncode, EXIT_OK)
            for message in ("v2", "paseo.claude_providers", "cấu hình Paseo"):
                self.assertIn(message, result.stderr)
        self.assertEqual(self.fx.calls(), [])

    def test_paseo_reloads_existing_agent_without_import(self) -> None:
        result = self.run_cli("paseo", "--session", SID_A)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        calls = self.fx.calls()
        self.assertEqual([call["argv"] for call in calls],
                         [["agent", "reload", AGENT_A]])
        self.assertIn("đã nạp lại", result.stdout)
        self.assertIn("mở Paseo trên điện thoại", result.stdout)

    def test_paseo_imports_when_session_has_no_agent(self) -> None:
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        calls = self.fx.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["argv"], [
            "import", SID_IMPORT, "--provider", "claude",
            "--cwd", str(self.fx.project.resolve()), "--json",
        ])
        self.assertIn(IMPORTED_AGENT, result.stdout)
        self.assertIn("đã import", result.stdout)
        self.assertIn("mở Paseo trên điện thoại", result.stdout)

    def test_paseo_live_tui_exits_four_without_paseo(self) -> None:
        result = self.run_cli("paseo", "--session", SID_TUI)
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stderr)
        self.assertIn(str(self.fx.tui_pid), result.stderr)
        self.assertIn("/exit", result.stderr)
        self.assertEqual(self.fx.calls(), [])

    def test_paseo_command_error_exits_five_with_short_stderr(self) -> None:
        result = self.run_cli("paseo", "--session", SID_IMPORT,
                              PASEO_FAKE_IMPORT_EXIT="1",
                              PASEO_FAKE_IMPORT_STDERR="provider offline\n")
        self.assertEqual(result.returncode, EXIT_PASEO, result.stderr)
        self.assertIn("provider offline", result.stderr)

    def test_paseo_picks_newest_transcript_with_a_user_line(self) -> None:
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        imported = self.calls("paseo")[0]["argv"][1]
        self.assertEqual(imported, SID_IMPORT)
        self.assertNotEqual(imported, SID_NO_USER)

    def test_paseo_prints_selected_session_title_and_mtime(self) -> None:
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        line = next(line for line in result.stdout.splitlines()
                    if line.startswith(f"session {SID_IMPORT[:8]}"))
        self.assertIn(f"— {TITLE_IMPORT} — sửa lúc ", line)
        self.assertRegex(line, r"sửa lúc \d{2}:\d{2}$")

    def test_paseo_prefers_handoff_over_newer_transcript_and_clears_it(self) -> None:
        self.seed_handoff(SID_A, AGENT_A)
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.calls("paseo")[0]["argv"],
                         ["agent", "reload", AGENT_A])
        self.assertIn("theo sổ bàn giao của `cc-switch term`", result.stdout)
        self.assertIn(f"session {SID_A[:8]} — {TITLE_A} — sửa lúc ", result.stdout)
        self.assertNotIn(str(self.fx.project.resolve()), self.handoff_entries())

    def test_paseo_falls_back_to_newest_when_handoff_transcript_is_gone(self) -> None:
        self.seed_handoff("dead0000-0000-0000-0000-000000000000", AGENT_A)
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.calls("paseo")[0]["argv"][1], SID_IMPORT)
        self.assertNotIn("theo sổ bàn giao", result.stdout)
        self.assertNotIn(str(self.fx.project.resolve()), self.handoff_entries())

    def test_paseo_ignores_newer_transcript_in_other_project_slug(self) -> None:
        path = (self.fx.projects / slugify(self.fx.other)
                / f"{SID_OTHER}.jsonl")
        path.write_text(json.dumps({
            "type": "user", "cwd": str(self.fx.project),
            "timestamp": "2099-01-01T00:00:00Z",
        }) + "\n", encoding="utf-8")
        os.utime(path, (time.time() + 100, time.time() + 100))
        result = self.run_cli("paseo")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.calls("paseo")[0]["argv"][1], SID_IMPORT)

    def test_paseo_uses_persistence_session_when_runtime_missing(self) -> None:
        result = self.run_cli("paseo", "--session", SID_P)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        reloaded = self.fx.calls()[0]["argv"]
        self.assertEqual(reloaded, ["agent", "reload", AGENT_P])

    def test_paseo_reloads_agent_even_without_transcript(self) -> None:
        result = self.run_cli("paseo", "--session", SID_ORPHAN)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(self.fx.calls()[0]["argv"],
                         ["agent", "reload", AGENT_ORPHAN])

    def test_paseo_dry_run_prints_import_without_calling_paseo(self) -> None:
        result = self.run_cli("paseo", "--dry-run")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertTrue(lines[0].startswith(f"session {SID_IMPORT[:8]} — "),
                        result.stdout)
        self.assertEqual(lines[-1], (
            f"paseo import {SID_IMPORT} --provider claude "
            f"--cwd {self.fx.project.resolve()} --json"))
        self.assertEqual(self.fx.calls(), [])

    # ---- status --------------------------------------------------------
    def test_status_prints_holder_for_each_agent(self) -> None:
        result = self.run_cli("status")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn("nơi đang giữ", result.stdout)
        lines = result.stdout.splitlines()
        row_a = next(line for line in lines if AGENT_A[:8] in line)
        row_tui = next(line for line in lines if AGENT_TUI[:8] in line)
        row_p = next(line for line in lines if AGENT_P[:8] in line)
        row_archived = next(line for line in lines if AGENT_ARCHIVED[:8] in line)
        self.assertIn("paseo", row_a)
        self.assertIn("terminal", row_tui)
        self.assertIn(str(self.fx.tui_pid), row_tui)
        self.assertIn(SID_P[:8], row_p)
        self.assertIn("không", row_archived)
        self.assertNotIn(AGENT_OTHER[:8], result.stdout)

    def test_status_all_includes_other_project(self) -> None:
        result = self.run_cli("status", "--all", cwd=self.fx.empty)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn(AGENT_OTHER[:8], result.stdout)

    # ---- secrets -------------------------------------------------------
    def test_key_and_forbidden_agent_fields_never_read_or_printed(self) -> None:
        self.assertEqual(self.fx.key_path.stat().st_mode & 0o777, 0)
        outputs = []
        for args in (("status",), ("term", "--agent", AGENT_A, "--dry-run"),
                     ("paseo", "--dry-run")):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            outputs.append(result.stdout + result.stderr)
        combined = "\n".join(outputs)
        for secret in (SECRET_KEY, SECRET_CONFIG, SECRET_NATIVE, SECRET_SOCKET,
                       SECRET_PROMPT):
            self.assertNotIn(secret, combined)
        for field in ("nativeHandle", "messagingSocketPath", '"config"'):
            self.assertNotIn(field, combined)


if __name__ == "__main__":
    unittest.main()
