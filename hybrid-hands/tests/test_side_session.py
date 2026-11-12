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
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
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
        legacy_config = self.tmp / "global.json"
        legacy_config.write_text(json.dumps({"side_session": {"transport": "screen"},
                                              "main_session": {"transport": "screen"}}))
        os.environ["HYBRID_HANDS_CONFIG"] = str(legacy_config)
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_DIR"] = str(self.tmp)
        os.environ["SIDE_SESSION_CLAUDE_PROJECTS"] = str(self.projects)
        os.environ["HYBRID_HANDS_STATE_DIR"] = str(self.machine)
        os.environ["SIDE_SESSION_NO_PASEO"] = "1"
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

    def test_claude_account_v2_config_and_resume(self):
        from side_session import handoff
        from side_session.commands import provider_argv
        template_root = self.tmp / "templates-fixture"
        (template_root / "templates").mkdir(parents=True)
        (template_root / "templates/side-session-prompt-claude.md").write_text("account={account}")
        (template_root / "templates/main-session-prompt-claude.md").write_text("main account={account}")
        with mock.patch.object(handoff, "PLUGIN_ROOT", template_root):
            args = ["start", "--name", "v2", "--provider", "claude", "--account", "v2", "--prompt", "task"]
            self.assertEqual(self.run_cli(*args)[0], 0)
            st = self.state("v2")
            self.assertEqual(st["claude_config_dir"], str(Path("~/.claude-hand").expanduser()))
            self.assertIn("account=v2", self.screen_log())
            self.assertEqual(self.run_cli("stop", "v2")[0], 0)
            self.assertEqual(self.run_cli("start", "--name", "v2", "--resume")[0], 0)
            self.assertEqual(self.state("v2")["account"], "v2")
            self.assertEqual(self.run_cli("start", "--name", "main-v2", "--main", "--provider", "claude", "--account", "v2")[0], 0)
            main = self.state("main-v2")
            self.assertEqual((main["role"], main["handoff"], main["watch_screen"]), ("main", "", ""))
        argv, env = provider_argv(load_config(self.repo), "claude", "x", "id", str(self.repo), "hi", account="v2")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], st["claude_config_dir"])
        self.assertEqual(argv[-5:], ["--model", "claude-opus-5-5", "--effort", "high", "hi"])
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(tokens.claude_transcript("/repo", "id", config_dir=st["claude_config_dir"]).parent.parent, Path(st["claude_config_dir"]) / "projects")

    def test_unknown_claude_account_rejected_before_mutation(self):
        from hand_ext.config import load_config as load_hand_config
        from side_session.config import claude_account, default_claude_accounts
        self.assertEqual(load_config(self.repo).claude_accounts, default_claude_accounts())
        from side_session.commands import provider_argv, session_cmd
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp / "inherited-v2")}):
            _, env = provider_argv(load_config(self.repo), "claude", "v1", "id", str(self.repo), "hi")
            self.assertNotIn("CLAUDE_CONFIG_DIR", env)
            command = session_cmd(load_config(self.repo), "claude", "v1", "id", str(self.repo), "hi")
            self.assertIn("unset CLAUDE_CONFIG_DIR;", command[-1])
        config = self.repo / ".claude" / "hybrid-hands.json"
        config.parent.mkdir()
        config.write_text(json.dumps({"ext_hand": {
            "claude_accounts": {"v3": {"config_dir": "third", "max_day_pct": 2}},
            "backends": {"claude-main": {"config_dir": "legacy-first"},
                         "claude-v2": {"config_dir": "canonical-second"}}}}))
        cfg = load_config(self.repo)
        self.assertEqual(cfg.claude_accounts, load_hand_config(known_root=self.repo).claude_accounts)
        for account, directory in (("v1", "legacy-first"), ("v2", "canonical-second"), ("v3", "third")):
            self.assertEqual(claude_account(cfg, account)["config_dir"], str((self.repo / directory).resolve()))
        self.assertEqual(cfg.claude_accounts["v3"]["max_day_pct"], 2)
        _, env = provider_argv(cfg, "claude", "v1", "id", str(self.repo), "hi")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str((self.repo / "legacy-first").resolve()))
        with mock.patch.object(actions.K, "worktree_cmd") as worktree, mock.patch.object(actions, "_preflight") as preflight:
            code, out = self.run_cli("start", "--name", "bad", "--provider", "claude", "--account", "v99", "--worktree", "--prompt", "task")
        self.assertEqual(code, 2)
        self.assertIn("account", out)
        worktree.assert_not_called()
        preflight.assert_not_called()
        self.assertFalse((self.repo / "output").exists())

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
        self.assertEqual(cfg.max_parallel, 4)
        self.assertEqual(cfg.worktree_root, (self.repo / ".." / "repo-wt").resolve())
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"side_session": {"max_parallel": 1}}))
        self.assertEqual(load_config(self.repo).max_parallel, 1)
        for value in (1, 4, 5, 6, 0, 7, True, False, "4", 1.5):
            (self.repo / ".claude" / "hybrid-hands.json").write_text(
                json.dumps({"side_session": {"max_parallel": value}}))
            if type(value) is int and 1 <= value <= 6:
                self.assertEqual(load_config(self.repo).max_parallel, value)
            else:
                with self.assertRaisesRegex(ValueError, r"số nguyên 1\.\.6"):
                    load_config(self.repo)

    def test_six_slot_guard_retains_unknown_and_idle_no_done(self) -> None:
        cfg = load_config(self.repo)
        cfg = replace(cfg, max_parallel=6)
        sessions = [SimpleNamespace(name=f"fake-{i}", role="", status=status,
                                   transport="paseo", provider="codex", handoff="fake", paseo_send_pending=False)
                    for i, status in enumerate(["running"] * 4 + ["unknown", "idle_no_done"])]
        args = SimpleNamespace(main=False, dry_run=False)
        with mock.patch.object(actions.state, "load_all", return_value=sessions), \
                mock.patch.object(actions.paseo, "refresh", side_effect=lambda _, st: st.status), \
                mock.patch.object(actions.K, "done_path", return_value=self.tmp / "missing.done"), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(len(actions._running(cfg)), 6)
            self.assertEqual(actions._preflight(cfg, args), 2)
            sessions.pop()
            self.assertIsNone(actions._preflight(cfg, args))

    def test_dry_run_prints_commands_and_creates_nothing(self) -> None:
        code, out = self.run_cli("start", "--name", "demo", "--provider", "claude",
                                 "--prompt", "x", "--worktree", "--hours", "3", "--dry-run")
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
        _, out = self.run_cli("start", "--name", "cx", "--prompt", "x", "--dry-run")
        self.assertIn("CODEX_HOME=", out)
        self.assertIn("exec codex -C", out)
        self.assertNotIn(" -p ", out.split("exec codex", 1)[1].split("\n", 1)[0])

    def test_start_ls_stop_and_parallel_limit(self) -> None:
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "hybrid-hands.json").write_text(
            json.dumps({"side_session": {"max_parallel": 2, "codex_home": str(self.tmp / "codex-home")}}))
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
        self.assertRegex(out, r"(?m)^a\s+codex\s+no\s+running\s+alive\s+\?")
        code, out = self.run_cli("stop", "a")
        self.assertEqual(code, 0)
        self.assertIn("-S 1234.side-a -X quit", self.screen_log())
        self.assertIn(".side-a-watch -X quit", self.screen_log())
        st = json.loads((self.repo / "output/llm/side-sessions/a.json").read_text())
        self.assertEqual(st["status"], "stopped")

    def test_watch_caps_session(self) -> None:
        self.run_cli("start", "--name", "w", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "1000")
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
        handoff.parent.mkdir(parents=True, exist_ok=True)
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

    def test_main_claude_prompt_names_launched_model(self) -> None:
        p = build_prompt("Task", "m", Path("/h/m.md"), "", account="v2", main=True,
                         model="claude-fable-5-2", effort="high")
        self.assertIn("Bạn là Fable 5.2 high Claude account v2", p)
        p = build_prompt("Task", "m", Path("/h/m.md"), "", account="v1", main=True)
        self.assertIn("Bạn là Opus 5.5 high Claude account v1", p)
        self.assertNotIn("{model_label}", p)

    def test_prompt_for_external_hand_does_not_ask_to_write_outside_worktree(self) -> None:
        p = build_prompt("Task", "n1", Path("/h/n1.md"), "main", external=True)
        self.assertNotIn("/h/n1.md", p)
        self.assertNotIn("SendMessage", p)
        self.assertIn("## Tóm tắt", p)
        self.assertIn("không ghi file ngoài thư mục làm việc", p)


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
