"""`cc-switch paseo --self`: detach a worker, close the TUI, hand off to Paseo."""
from __future__ import annotations

import contextlib
import io
import os
import signal
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

from cc_fixture import (  # noqa: E402
    AGENT_TUI, CcFixture, NOW, SID_A, SID_IMPORT, SID_TUI, slugify,
)
from cc_switch import proc, self_cmd  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4
TIMEOUT = 30
SID_STUBBORN = "51000000-0000-0000-0000-000000000010"
SID_NO_TRANSCRIPT = "dead0000-0000-0000-0000-000000000000"


class CcSwitchSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = CcFixture()
        self.addCleanup(self.fx.close)

    def run_cli(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BIN), *args],
            cwd=str(self.fx.project), env=self.fx.env(**env),
            capture_output=True, text=True, timeout=TIMEOUT,
        )

    def calls(self, command: str) -> list:
        return [call for call in self.fx.calls() if call["cmd"] == command]

    def log_path(self, session_id: str) -> Path:
        return (self.fx.state / "cc-switch"
                / f"self-{session_id[:8]}.log")

    def spawn_sleeper(self) -> subprocess.Popen:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"])
        self.addCleanup(process.wait, 5)
        self.addCleanup(process.terminate)
        return process

    # ---- parent --------------------------------------------------------
    def test_paseo_help_lists_self_flags(self) -> None:
        result = self.run_cli("paseo", "--help")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        for flag in ("--self", "--idle-sec", "--exit-timeout"):
            self.assertIn(flag, result.stdout)

    def test_self_without_session_env_exits_two_with_hint(self) -> None:
        result = self.run_cli("paseo", "--self", CLAUDE_CODE_SESSION_ID="")
        self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
        self.assertIn("CLAUDE_CODE_SESSION_ID", result.stderr)
        self.assertIn("--session", result.stderr)
        self.assertEqual(self.fx.calls(), [])

    def test_self_without_live_tui_exits_three(self) -> None:
        result = self.run_cli("paseo", "--self",
                              CLAUDE_CODE_SESSION_ID=SID_IMPORT)
        self.assertEqual(result.returncode, EXIT_NOT_FOUND, result.stderr)
        self.assertIn("không mở trong terminal", result.stderr)
        self.assertIn("Paseo", result.stderr)
        self.assertEqual(self.fx.calls(), [])

    def test_self_with_several_tui_pids_and_no_ancestor_exits_four(self) -> None:
        first = self.spawn_sleeper()
        second = self.spawn_sleeper()
        self.fx.add_live_session(first.pid, SID_TUI)
        self.fx.add_live_session(second.pid, SID_TUI)
        result = self.run_cli("paseo", "--self",
                              CLAUDE_CODE_SESSION_ID=SID_TUI)
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stderr)
        self.assertIn("nhiều terminal", result.stderr)
        self.assertIn(str(self.fx.tui_pid), result.stderr)
        self.assertFalse(self.log_path(SID_TUI).exists())
        self.assertEqual(self.fx.calls(), [])

    def test_self_with_session_is_usage_error(self) -> None:
        result = self.run_cli("paseo", "--self", "--session", SID_A)
        self.assertEqual(result.returncode, EXIT_USAGE, result.stderr)
        self.assertIn("không đi cùng", result.stderr)
        self.assertFalse(self.log_path(SID_A).exists())
        self.assertEqual(self.fx.calls(), [])

    def test_self_dry_run_prints_plan_without_spawning(self) -> None:
        result = self.run_cli("paseo", "--self", "--dry-run",
                              CLAUDE_CODE_SESSION_ID=SID_TUI)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn(f"phiên {SID_TUI[:8]}", result.stdout)
        self.assertIn(f"TUI pid {self.fx.tui_pid}", result.stdout)
        self.assertIn(str(self.log_path(SID_TUI)), result.stdout)
        self.assertIn("SIGTERM", result.stdout)
        self.assertIn("cc-switch term", result.stdout)
        self.assertFalse(self.log_path(SID_TUI).exists())
        self.assertEqual(self.fx.calls(), [])

    def test_self_spawns_detached_worker_with_expected_argv(self) -> None:
        env = {
            "CLAUDE_CODE_SESSION_ID": SID_TUI,
            "CLAUDE_CONFIG_DIR": str(self.fx.claude),
            "HYBRID_HANDS_STATE_DIR": str(self.fx.state),
            "PASEO_HOME": str(self.fx.paseo),
            "PATH": self.fx.env()["PATH"],
        }
        opts = SimpleNamespace(session=None, self_mode=True, dry_run=False,
                               idle_sec=7, exit_timeout=9)
        worker = mock.Mock(pid=4242)
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(self_cmd, "process_alive", return_value=True), \
                mock.patch("cc_switch.sessions.process_alive",
                           return_value=True), \
                mock.patch.object(self_cmd.subprocess, "Popen",
                                  return_value=worker) as popen, \
                contextlib.redirect_stdout(output):
            code = self_cmd.run_paseo_self(opts)
        self.assertEqual(code, EXIT_OK, output.getvalue())
        popen.assert_called_once()
        argv, kwargs = popen.call_args
        self.assertEqual(argv[0][:3], [
            sys.executable, str(BIN.resolve()), "_self-worker",
        ])
        self.assertEqual(argv[0][3:], [
            "--session", SID_TUI,
            "--pid", str(self.fx.tui_pid),
            "--cwd", str(self.fx.project.resolve()),
            "--idle-sec", "7",
            "--exit-timeout", "9",
        ])
        self.assertIs(kwargs["start_new_session"], True)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.STDOUT)
        self.assertEqual(kwargs["cwd"], str(self.fx.project.resolve()))
        self.assertEqual(kwargs["stdout"].name, str(self.log_path(SID_TUI)))
        self.assertIn("Đã tách tiến trình nền pid 4242", output.getvalue())
        self.assertIn("Đừng gõ", output.getvalue())
        log_text = self.log_path(SID_TUI).read_text(encoding="utf-8")
        self.assertIn("nhận lệnh --self", log_text)

    def test_self_parent_spawns_a_real_worker(self) -> None:
        result = self.run_cli(
            "paseo", "--self", "--idle-sec", "0", "--exit-timeout", "10",
            CLAUDE_CODE_SESSION_ID=SID_TUI)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn(str(self.log_path(SID_TUI)), result.stdout)
        self.assertEqual(self.fx.sleeper.wait(timeout=10), -signal.SIGTERM)

        log_path = self.log_path(SID_TUI)
        log_text = ""
        for _ in range(100):
            if log_path.exists():
                log_text = log_path.read_text(encoding="utf-8")
                if "xong (mã 0)" in log_text:
                    break
            time.sleep(0.1)
        self.assertIn("bắt đầu: phiên", log_text)
        self.assertIn("xong (mã 0)", log_text)
        calls = [call["argv"] for call in self.calls("paseo")]
        self.assertIn(["agent", "reload", AGENT_TUI], calls)

    # ---- worker --------------------------------------------------------
    def test_wait_for_idle_uses_mtime_and_deadline(self) -> None:
        path = self.fx.base / "idle.jsonl"
        path.write_text("x", encoding="utf-8")
        old = time.time() - 10
        os.utime(path, (old, old))
        self.assertTrue(self_cmd.wait_for_idle(
            path, 1, max_wait_seconds=2, poll_seconds=0.05))

        fresh = time.time()
        os.utime(path, (fresh, fresh))
        started = time.monotonic()
        self.assertFalse(self_cmd.wait_for_idle(
            path, 60, max_wait_seconds=0.2, poll_seconds=0.05))
        self.assertGreaterEqual(time.monotonic() - started, 0.15)

    def test_select_tui_pid_prefers_ancestor_for_several(self) -> None:
        self.assertEqual(proc.select_tui_pid([7]), 7)
        with mock.patch.object(proc, "ancestors",
                               return_value=[100, 200]):
            self.assertEqual(
                proc.select_tui_pid([200, 300], current_pid=400), 200)
            self.assertIsNone(
                proc.select_tui_pid([300, 400], current_pid=999))
        with mock.patch.object(proc, "ancestors", return_value=None):
            self.assertIsNone(proc.select_tui_pid([200, 300]))

    def test_worker_sigterms_tui_then_reloads_paseo(self) -> None:
        transcript = (self.fx.projects / slugify(self.fx.project)
                      / f"{SID_TUI}.jsonl")
        fresh = time.time()
        os.utime(transcript, (fresh, fresh))
        started = time.monotonic()
        worker = subprocess.Popen(
            [sys.executable, str(BIN), "_self-worker",
             "--session", SID_TUI, "--pid", str(self.fx.tui_pid),
             "--cwd", str(self.fx.project), "--idle-sec", "1",
             "--exit-timeout", "10"],
            env=self.fx.env(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        try:
            code = self.fx.sleeper.wait(timeout=10)
            output, _ = worker.communicate(timeout=TIMEOUT)
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=5)
        self.assertGreaterEqual(time.monotonic() - started, 0.8)
        self.assertEqual(code, -signal.SIGTERM)
        self.assertEqual(worker.returncode, EXIT_OK, output)
        self.assertIn(f"gửi SIGTERM tới TUI pid {self.fx.tui_pid}", output)
        self.assertIn("TUI pid", output)
        self.assertIn("đã thoát", output)
        self.assertIn("xong (mã 0)", output)
        self.assertRegex(output, r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")
        reloads = [call["argv"] for call in self.calls("paseo")]
        self.assertIn(["agent", "reload", AGENT_TUI], reloads)

    def test_worker_does_not_signal_a_tui_of_another_session(self) -> None:
        other = self.spawn_sleeper()
        self.fx.add_live_session(other.pid, SID_A)
        result = self.run_cli(
            "_self-worker", "--session", SID_A,
            "--pid", str(self.fx.tui_pid), "--cwd", str(self.fx.project),
            "--idle-sec", "0", "--exit-timeout", "0")
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stdout)
        self.assertIn("không còn là TUI của phiên", result.stdout)
        self.assertIsNone(self.fx.sleeper.poll())
        self.assertEqual(self.fx.calls(), [])

    def test_worker_gives_up_when_pid_ignores_sigterm(self) -> None:
        stubborn = subprocess.Popen(
            [sys.executable, "-c",
             "import signal,sys,time; "
             "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "sys.stdout.write('ready\\n'); sys.stdout.flush(); "
             "time.sleep(300)"],
            stdout=subprocess.PIPE, text=True)
        # Cleanups run LIFO: kill, reap, then close the pipe even on failure.
        self.addCleanup(stubborn.stdout.close)
        self.addCleanup(stubborn.wait, 5)
        self.addCleanup(stubborn.kill)
        self.assertEqual(stubborn.stdout.readline().strip(), "ready")
        self.fx.add_live_session(stubborn.pid, SID_STUBBORN)
        self.fx.add_transcript(self.fx.project, SID_STUBBORN, mtime=NOW - 10)
        result = self.run_cli(
            "_self-worker", "--session", SID_STUBBORN,
            "--pid", str(stubborn.pid), "--cwd", str(self.fx.project),
            "--idle-sec", "0", "--exit-timeout", "1")
        self.assertEqual(result.returncode, EXIT_CONFLICT, result.stdout)
        self.assertIn("chưa thoát", result.stdout)
        self.assertIn("không SIGKILL", result.stdout)
        self.assertIsNone(stubborn.poll())
        self.assertEqual(self.fx.calls(), [])

    def test_worker_without_transcript_exits_three(self) -> None:
        result = self.run_cli(
            "_self-worker", "--session", SID_NO_TRANSCRIPT,
            "--pid", str(self.fx.tui_pid), "--cwd", str(self.fx.project),
            "--idle-sec", "0", "--exit-timeout", "0")
        self.assertEqual(result.returncode, EXIT_NOT_FOUND, result.stdout)
        self.assertIn("không tìm thấy transcript", result.stdout)
        self.assertIsNone(self.fx.sleeper.poll())
        self.assertEqual(self.fx.calls(), [])


if __name__ == "__main__":
    unittest.main()
