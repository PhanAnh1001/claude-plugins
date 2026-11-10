"""`cc-switch term --self`: detach, wait for idle, open a Terminal window."""
from __future__ import annotations

import contextlib
import io
import os
import shlex
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent / "plugins" / "hybrid-hands"
BIN = PLUGIN / "bin" / "cc-switch"
LIB = PLUGIN / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(TESTS / "fixtures" / "cc_switch"))

from cc_fixture import AGENT_A, CcFixture, SID_A, SID_IMPORT, SID_TUI  # noqa: E402
from cc_switch import cli, term_self  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
TIMEOUT = 30


class CcSwitchTermSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = CcFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BIN), *args],
            cwd=str(self.fx.project), env=self.fx.env(**env),
            capture_output=True, text=True, timeout=TIMEOUT,
        )

    def log_path(self, session_id: str) -> Path:
        return (self.fx.state / "cc-switch"
                / f"self-{session_id[:8]}.log")

    # ---- parent --------------------------------------------------------
    def test_term_help_lists_self_flags(self) -> None:
        result = self.run_cli("term", "--help")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        for flag in ("--self", "--idle-sec", "--app"):
            self.assertIn(flag, result.stdout)

    def test_self_without_session_env_exits_two_with_hint(self) -> None:
        result = self.run_cli("term", "--self", CLAUDE_CODE_SESSION_ID="")
        self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
        self.assertIn("CLAUDE_CODE_SESSION_ID", result.stderr)
        self.assertIn("--session", result.stderr)
        self.assertFalse(self.log_path(SID_A).exists())
        self.assertEqual(self.fx.open_calls(), [])

    def test_self_with_live_tui_exits_four(self) -> None:
        result = self.run_cli("term", "--self",
                              CLAUDE_CODE_SESSION_ID=SID_TUI)
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stderr)
        self.assertIn("đã mở trong terminal", result.stderr)
        self.assertIn(str(self.fx.tui_pid), result.stderr)
        self.assertFalse(self.log_path(SID_TUI).exists())
        self.assertEqual(self.fx.open_calls(), [])

    def test_self_without_paseo_agent_exits_three_with_hint(self) -> None:
        result = self.run_cli("term", "--self",
                              CLAUDE_CODE_SESSION_ID=SID_IMPORT)
        self.assertEqual(result.returncode, EXIT_NOT_FOUND, result.stderr)
        self.assertIn("không do Paseo giữ", result.stderr)
        self.assertIn("cc-switch term --session", result.stderr)
        self.assertFalse(self.log_path(SID_IMPORT).exists())
        self.assertEqual(self.fx.open_calls(), [])

    def test_self_with_agent_or_session_is_usage_error(self) -> None:
        for extra in (("--agent", AGENT_A), ("--session", SID_A)):
            result = self.run_cli("term", "--self", *extra,
                                  CLAUDE_CODE_SESSION_ID=SID_A)
            self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
            self.assertIn("không đi cùng", result.stderr)
            self.assertFalse(self.log_path(SID_A).exists())
        self.assertEqual(self.fx.open_calls(), [])

    def test_self_rejects_extra_args_after_double_dash(self) -> None:
        result = self.run_cli("term", "--self", "--", "--verbose",
                              CLAUDE_CODE_SESSION_ID=SID_A)
        self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
        self.assertIn("không nhận đối số sau `--`", result.stderr)
        self.assertFalse(self.log_path(SID_A).exists())

    def test_self_on_non_darwin_exits_two(self) -> None:
        env = self.fx.env(CLAUDE_CODE_SESSION_ID=SID_A)
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(term_self.sys, "platform", "linux"), \
                contextlib.redirect_stderr(output):
            code = cli.main(["term", "--self"])
        self.assertEqual(code, EXIT_USAGE, output.getvalue())
        self.assertIn("macOS", output.getvalue())
        self.assertIn("linux", output.getvalue())
        self.assertFalse(self.log_path(SID_A).exists())

    def test_self_dry_run_prints_plan_without_spawning(self) -> None:
        result = self.run_cli("term", "--self", "--dry-run",
                              CLAUDE_CODE_SESSION_ID=SID_A)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        for text in (f"phiên {SID_A[:8]}", f"agent {AGENT_A[:8]}",
                     str(self.fx.project.resolve()), "Terminal",
                     "cc-switch term --session", str(self.log_path(SID_A))):
            self.assertIn(text, result.stdout)
        self.assertIn("kế hoạch", result.stdout)
        self.assertFalse(self.log_path(SID_A).exists())
        self.assertEqual(self.fx.open_calls(), [])

    def test_self_dry_run_does_not_call_popen(self) -> None:
        env = self.fx.env(CLAUDE_CODE_SESSION_ID=SID_A)
        opts = SimpleNamespace(agent=None, session=None, self_mode=True,
                               dry_run=True, idle_sec=20, app="Terminal",
                               extra=[])
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch("cc_switch.sessions.process_alive",
                           return_value=False), \
                mock.patch.object(term_self, "spawn_worker") as spawn, \
                contextlib.redirect_stdout(output):
            code = term_self.run_term_self(opts)
        self.assertEqual(code, EXIT_OK, output.getvalue())
        spawn.assert_not_called()
        self.assertIn(f"phiên {SID_A[:8]}", output.getvalue())
        self.assertFalse(self.log_path(SID_A).exists())

    def test_self_spawns_detached_worker_with_expected_argv(self) -> None:
        env = self.fx.env(CLAUDE_CODE_SESSION_ID=SID_A)
        opts = SimpleNamespace(agent=None, session=None, self_mode=True,
                               dry_run=False, idle_sec=7, app="Terminal",
                               extra=[])
        worker = mock.Mock(pid=4242)
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch("cc_switch.sessions.process_alive",
                           return_value=False), \
                mock.patch.object(term_self.subprocess, "Popen",
                                  return_value=worker) as popen, \
                contextlib.redirect_stdout(output):
            code = term_self.run_term_self(opts)
        self.assertEqual(code, EXIT_OK, output.getvalue())
        popen.assert_called_once()
        argv, kwargs = popen.call_args
        self.assertEqual(argv[0][:3], [
            sys.executable, str(BIN.resolve()), "_term-worker",
        ])
        self.assertEqual(argv[0][3:], [
            "--session", SID_A,
            "--cwd", str(self.fx.project.resolve()),
            "--idle-sec", "7",
            "--app", "Terminal",
        ])
        self.assertIs(kwargs["start_new_session"], True)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.STDOUT)
        self.assertEqual(kwargs["cwd"], str(self.fx.project.resolve()))
        self.assertEqual(kwargs["stdout"].name, str(self.log_path(SID_A)))
        self.assertIn("Đã tách tiến trình nền pid 4242", output.getvalue())
        self.assertIn("sẽ mở sau khi lượt này xong", output.getvalue())
        self.assertIn("/to-paseo", output.getvalue())
        self.assertIn("cc-switch paseo", output.getvalue())
        log_text = self.log_path(SID_A).read_text(encoding="utf-8")
        self.assertIn("nhận lệnh term --self", log_text)
        self.assertEqual(self.fx.open_calls(), [])

    # ---- worker --------------------------------------------------------
    def test_worker_opens_terminal_with_quoted_cwd_and_session(self) -> None:
        weird = self.fx.base / 'cwd có "nháy" và khoảng trắng'
        weird.mkdir()
        cwd_text = str(weird)
        self.fx.add_transcript(self.fx.project, SID_A, mtime=time.time())
        started = time.monotonic()
        result = self.run_cli(
            "_term-worker", "--session", SID_A, "--cwd", cwd_text,
            "--idle-sec", "1", "--app", "Terminal")
        self.assertGreaterEqual(time.monotonic() - started, 0.8)
        self.assertEqual(result.returncode, EXIT_OK, result.stdout)
        self.assertIn("transcript đã đứng yên", result.stdout)
        self.assertIn("đã mở cửa sổ Terminal", result.stdout)
        calls = self.fx.open_calls()
        self.assertEqual(len(calls), 1)

        shell = "cd {} && exec {} term --session {}".format(
            shlex.quote(cwd_text), shlex.quote(str(BIN.resolve())),
            shlex.quote(SID_A))
        script_path = calls[0]["argv"][-1]
        self.assertEqual(calls[0]["argv"], ["-a", "Terminal", script_path])
        self.assertTrue(script_path.endswith(".command"), script_path)
        self.assertEqual(calls[0]["script"], f"#!/bin/zsh\n{shell}\n")
        self.assertEqual(calls[0]["mode"], "0o700")
        self.assertEqual(self.fx.calls(), [])
        self.assertIsNone(self.fx.sleeper.poll())

    def test_worker_open_error_exits_nonzero_and_logs_stderr(self) -> None:
        result = self.run_cli(
            "_term-worker", "--session", SID_A,
            "--cwd", str(self.fx.project), "--idle-sec", "0",
            "--app", "Terminal",
            CC_SWITCH_OPEN_EXIT="1",
            CC_SWITCH_OPEN_STDERR="Unable to find application named Terminal\n")
        self.assertNotEqual(result.returncode, EXIT_OK, result.stdout)
        self.assertIn("open lỗi", result.stdout)
        self.assertIn("Unable to find application", result.stdout)
        self.assertEqual(len(self.fx.open_calls()), 1)
        self.assertEqual(self.fx.calls(), [])

    def test_worker_does_not_open_when_tui_is_alive(self) -> None:
        self.fx.add_live_session(self.fx.sleeper.pid, SID_A)
        result = self.run_cli(
            "_term-worker", "--session", SID_A,
            "--cwd", str(self.fx.project), "--idle-sec", "0",
            "--app", "Terminal")
        self.assertNotEqual(result.returncode, EXIT_OK, result.stdout)
        self.assertIn("TUI của phiên vẫn còn sống", result.stdout)
        self.assertIn(str(self.fx.sleeper.pid), result.stdout)
        self.assertEqual(self.fx.open_calls(), [])

    def test_worker_without_transcript_exits_three(self) -> None:
        result = self.run_cli(
            "_term-worker", "--session", "dead0000-0000-0000-0000-000000000000",
            "--cwd", str(self.fx.project), "--idle-sec", "0",
            "--app", "Terminal")
        self.assertEqual(result.returncode, EXIT_NOT_FOUND, result.stdout)
        self.assertIn("không tìm thấy transcript", result.stdout)
        self.assertEqual(self.fx.open_calls(), [])

    # ---- slash commands -------------------------------------------------
    def test_plugin_slash_commands_exist_and_name_the_right_command(self) -> None:
        expected = {
            "to-paseo": ("cc-switch paseo --self", "TUI tự đóng"),
            "to-term": ("cc-switch term --self", "đừng gửi tin"),
        }
        for name, (command, reminder) in expected.items():
            path = PLUGIN / "commands" / f"{name}.md"
            self.assertTrue(path.is_file(), str(path))
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), text[:40])
            frontmatter = text.split("---", 2)[1]
            self.assertIn("description:", frontmatter)
            self.assertIn("allowed-tools: Bash", frontmatter)
            self.assertIn(command, text)
            self.assertIn("tool Bash", text)
            self.assertIn(reminder.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
