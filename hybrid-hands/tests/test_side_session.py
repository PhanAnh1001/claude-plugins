"""Tests for side-session with fake screen/claude/codex on a temp PATH (no real sessions)."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PL = ROOT / "plugins" / "hybrid-hands"
FIX = ROOT / "tests" / "fixtures" / "side_session"
sys.path.insert(0, str(PL / "lib"))

from side_session import actions, cli, tokens  # noqa: E402
from side_session.config import load_config  # noqa: E402
from side_session.handoff import build_prompt, summary_block  # noqa: E402

FAKE_SCREEN = """#!/bin/sh
echo "$@" >> "$FAKE_DIR/screen.log"
case "$1" in
  -ls) while read n; do printf '\\t1234.%s\\t(Detached)\\n' "$n"; done < "$FAKE_DIR/alive"; exit 1;;
  -dmS) echo "$2" >> "$FAKE_DIR/alive";;
  -S) grep -vx "${2#*.}" "$FAKE_DIR/alive" > "$FAKE_DIR/alive.new"; mv "$FAKE_DIR/alive.new" "$FAKE_DIR/alive";;
esac
"""
FAKE_FAIL = "#!/bin/sh\necho fake-must-not-run >&2\nexit 99\n"


class SideSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="side-session-test-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        for name, body in (("screen", FAKE_SCREEN), ("claude", FAKE_FAIL), ("codex", FAKE_FAIL)):
            (bindir / name).write_text(body)
            (bindir / name).chmod(0o755)
        (self.tmp / "alive").write_text("")
        self.projects = self.tmp / "projects"
        self.machine = self.tmp / "machine"
        self._env = dict(os.environ)
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_DIR"] = str(self.tmp)
        os.environ["SIDE_SESSION_CLAUDE_PROJECTS"] = str(self.projects)
        os.environ["HYBRID_HANDS_STATE_DIR"] = str(self.machine)
        self._cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp)  # only our own mkdtemp dir

    def run_cli(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def screen_log(self) -> str:
        log = self.tmp / "screen.log"
        return log.read_text() if log.exists() else ""

    def state(self, name: str) -> dict:
        return json.loads((self.repo / "output/llm/side-sessions" / f"{name}.json").read_text())

    def start_ext(self, name: str) -> int:
        with mock.patch.object(actions.K, "worktree_cmd", return_value=["true"]):
            code, _ = self.run_cli("start", "--name", name, "--provider", "dsh",
                                   "--worktree", "--prompt",
                                   "## LUẬT BẮT BUỘC\n- Không đọc .env.\n")
        return code

    def write_run(self, st: dict, *, status: str = "running", label: str | None = None,
                  started: float | None = None, report: str | None = None) -> None:
        run_dir = self.tmp / "run-1"
        run_dir.mkdir(exist_ok=True)
        if report is not None:
            (run_dir / "report.md").write_text(report)
        run_started = st["started"] + 1 if started is None else started
        data = {"run_id": "run-1", "label": label or f"side:{st['name']}",
                "backend": st["provider"],
                "status": status, "tokens": {"input": 1200, "cached_input": 999,
                                             "output": 34},
                "started": run_started, "ended": run_started + 1, "run_dir": str(run_dir),
                "pid": os.getpid()}
        runs = self.machine / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "run-1.json").write_text(json.dumps(data))

    def test_config_defaults_and_override(self) -> None:
        cfg = load_config(self.repo)
        self.assertEqual(cfg.max_parallel, 2)
        self.assertEqual(cfg.worktree_root, (self.repo / ".." / "repo-wt").resolve())
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"side_session": {"max_parallel": 1}}))
        self.assertEqual(load_config(self.repo).max_parallel, 1)

    def test_dry_run_prints_commands_and_creates_nothing(self) -> None:
        code, out = self.run_cli("start", "--name", "demo", "--prompt", "x", "--worktree",
                                 "--hours", "3", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("worktree add", out)
        self.assertIn("-b side/demo HEAD", out)
        self.assertIn("screen -dmS side-demo", out)
        self.assertIn("--permission-mode bypassPermissions --no-chrome", out)
        self.assertIn("side-demo-watch", out)
        self.assertIn("max_tokens=450000", out)
        self.assertEqual(self.screen_log().count("-dmS"), 0)
        self.assertFalse((self.repo / "output").exists())

    def test_codex_dry_run(self) -> None:
        _, out = self.run_cli("start", "--name", "cx", "--prompt", "x",
                              "--provider", "codex", "--dry-run")
        self.assertIn("CODEX_HOME=", out)
        self.assertIn("exec codex -C", out)
        self.assertNotIn(" -p ", out.split("exec codex", 1)[1].split("\n", 1)[0])

    def test_start_ls_stop_and_parallel_limit(self) -> None:
        for name in ("a", "b"):
            code, _ = self.run_cli("start", "--name", name, "--prompt", "do it")
            self.assertEqual(code, 0)
        code, out = self.run_cli("start", "--name", "c", "--prompt", "x")
        self.assertEqual(code, 2)
        self.assertIn("max_parallel", out)
        st = json.loads((self.repo / "output/llm/side-sessions/a.json").read_text())
        self.assertEqual(st["status"], "running")
        _, out = self.run_cli("ls")
        self.assertIn("alive", out)
        self.assertIn("0/300000", out)
        code, out = self.run_cli("stop", "a")
        self.assertEqual(code, 0)
        self.assertIn("-S 1234.side-a -X quit", self.screen_log())
        self.assertIn(".side-a-watch -X quit", self.screen_log())
        st = json.loads((self.repo / "output/llm/side-sessions/a.json").read_text())
        self.assertEqual(st["status"], "stopped")

    def test_watch_caps_session(self) -> None:
        self.run_cli("start", "--name", "w", "--prompt", "x", "--max-tokens", "1000")
        st = json.loads((self.repo / "output/llm/side-sessions/w.json").read_text())
        tdir = self.projects / tokens.project_slug(st["dir"])
        tdir.mkdir(parents=True)
        shutil.copy(FIX / "claude_transcript.jsonl", tdir / f"{st['uuid']}.jsonl")
        code, out = self.run_cli("watch", "--name", "w", "--once")
        self.assertEqual(code, 0)
        self.assertIn("capped", out)
        st = json.loads((self.repo / "output/llm/side-sessions/w.json").read_text())
        self.assertEqual(st["status"], "capped")
        self.assertEqual(st["tokens_used"], 1615)
        self.assertIn("-S 1234.side-w -X quit", self.screen_log())

    def test_watch_reads_ext_tokens_and_copies_report(self) -> None:
        self.assertEqual(self.start_ext("x"), 0)
        st = self.state("x")
        self.write_run(st)
        self.run_cli("watch", "--name", "x", "--once")
        # input includes cached in hand-ext; cached is subtracted (claude counter parity)
        self.assertEqual(self.state("x")["tokens_used"], 235)
        self.assertEqual(self.state("x")["status"], "running")
        self.assertIn("235/300000", self.run_cli("ls")[1])
        self.write_run(st, status="ok", report="## Tóm tắt\n- Kết quả: xong\n")
        self.run_cli("watch", "--name", "x", "--once")
        final = self.state("x")
        self.assertEqual(final["status"], "stopped")
        self.assertEqual(Path(final["handoff"]).read_text(),
                         "## Tóm tắt\n- Kết quả: xong\n")

    def test_watch_ext_failed_run_marks_dead(self) -> None:
        self.assertEqual(self.start_ext("bad"), 0)
        self.write_run(self.state("bad"), status="failed")
        self.run_cli("watch", "--name", "bad", "--once")
        self.assertEqual(self.state("bad")["status"], "dead")

    def test_watch_ext_accepts_sanitized_label_and_keeps_existing_handoff(self) -> None:
        self.assertEqual(self.start_ext("san"), 0)
        st = self.state("san")
        handoff = Path(st["handoff"])
        handoff.parent.mkdir(parents=True)
        handoff.write_text("bàn giao cũ")
        self.write_run(st, status="ok", label="side-san", report="mới")
        self.run_cli("watch", "--name", "san", "--once")
        self.assertEqual(self.state("san")["status"], "stopped")
        self.assertEqual(handoff.read_text(), "bàn giao cũ")

    def test_watch_ext_accepts_registry_second_precision(self) -> None:
        self.assertEqual(self.start_ext("sec"), 0)
        st = self.state("sec")
        st["started"] = 100.9
        (self.repo / "output/llm/side-sessions/sec.json").write_text(json.dumps(st))
        self.write_run(st, status="ok", started=100.0)  # RunRegistry truncates to seconds
        self.run_cli("watch", "--name", "sec", "--once")
        self.assertEqual(self.state("sec")["status"], "stopped")

    def test_token_counters(self) -> None:
        self.assertEqual(tokens.claude_tokens(FIX / "claude_transcript.jsonl"), 1615)
        self.assertEqual(tokens.codex_tokens(FIX / "codex_rollout.jsonl"), 4500)
        self.assertEqual(tokens.project_slug("/home/x/app/a.b"), "-home-x-app-a-b")

    def test_handoff_summary(self) -> None:
        block = summary_block(FIX / "handoff.md")
        self.assertTrue(block.startswith("## Tóm tắt"))
        self.assertNotIn("Chi tiết", block)
        hdir = self.repo / "docs/work-in-progress/handoffs"
        hdir.mkdir(parents=True)
        shutil.copy(FIX / "handoff.md", hdir / "h.md")
        code, out = self.run_cli("handoff", "h")
        self.assertEqual(code, 0)
        self.assertIn("Kết quả: xong", out)
        self.assertEqual(self.run_cli("handoff", "none")[0], 1)

    def test_prompt_brain_line(self) -> None:
        p = build_prompt("Task", "n1", Path("/h/n1.md"), "")
        self.assertNotIn("brain", p)
        self.assertIn("SendMessage", p)  # parallel-session write notice stays
        p = build_prompt("Task", "n1", Path("/h/n1.md"), "main")
        self.assertIn('phiên brain "main"', p)
        self.assertIn("/h/n1.md", p)


if __name__ == "__main__":
    unittest.main()


class ScreenQuitExactTest(unittest.TestCase):
    """`screen -S side-x` also matches `side-x-watch`; quitting must target pid.name."""

    LS = ("There are screens on:\n\t111.side-x\t(Detached)\n"
          "\t222.side-x-watch\t(Detached)\n2 Sockets in /tmp.\n")

    def test_quit_targets_exact_pid_name(self) -> None:
        from side_session import screen
        done = subprocess.CompletedProcess([], 0, stdout=self.LS, stderr="")
        with mock.patch.object(screen.subprocess, "run", return_value=done) as run:
            screen.quit("side-x")
        self.assertEqual(run.call_args_list[-1].args[0],
                         ["screen", "-S", "111.side-x", "-X", "quit"])
