"""side_session codex specifics: optional -p, rollout filtered by session start, trust, tokens."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from side_session import actions, constants as C, state, tokens  # noqa: E402
from side_session.commands import (HAND_EXT_BIN, build_codex_prompt,  # noqa: E402
                                   codex_argv, provider_argv)
from side_session.cli import build_parser
from side_session.config import SideConfig  # noqa: E402

OLD_AGE_S = 3600  # an earlier hand-gpt run finished an hour before the session


def normalise(path: str | Path) -> Path:
    """Resolve both sides so /var and /private/var compare equal on macOS."""
    return Path(path).resolve()


def write_rollout(path: Path, cwd: Path, created: float, total: dict | None = None,
                  last: dict | None = None) -> Path:
    """A real-shaped rollout: session_meta first, token_count next."""
    stamp = datetime.fromtimestamp(created, timezone.utc).isoformat()
    records = [{"type": "session_meta",
                "payload": {"id": "codex-session-id", "cwd": str(cwd), "timestamp": stamp}},
               {"type": "event_msg", "payload": {"type": "token_count", "info": {
                   "total_token_usage": total or {},
                   "last_token_usage": last or total or {}}}}]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


class CodexArgvTest(unittest.TestCase):
    def _cfg(self, profile: str) -> SimpleNamespace:
        return SimpleNamespace(
            codex_profile=profile, codex_home=Path("/h"), claude_args=[],
            codex_model=C.CODEX_MODEL_DEFAULT, codex_effort=C.CODEX_EFFORT_DEFAULT,
            repo=Path("/repo"), worktree_root=Path("/repo-wt"),
            handoff_dir=Path("/repo/docs/handoffs"))

    def test_default_profile_is_empty(self):
        self.assertEqual(C.DEFAULTS["codex_profile"], "")

    def test_no_p_flag_when_profile_empty(self):
        argv, env = provider_argv(self._cfg(""), C.PROVIDER_CODEX, "n", "u", "/w", "hi")
        self.assertNotIn("-p", argv)
        self.assertEqual(env["CODEX_HOME"], "/h")

    def test_p_flag_when_profile_set(self):
        argv, _ = provider_argv(self._cfg("x"), C.PROVIDER_CODEX, "n", "u", "/w", "hi")
        self.assertEqual(argv[1:3], ["-p", "x"])

    def test_model_effort_approval_and_sandbox_argv(self):
        with mock.patch.dict(os.environ, {"HYBRID_HANDS_STATE_DIR": ""}):
            argv, _ = provider_argv(self._cfg(""), C.PROVIDER_CODEX, "n", "u", "/w", "hi")
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6.1-sol")
        self.assertIn('model_reasoning_effort="high"', argv)
        self.assertEqual(argv[argv.index("-a") + 1], "never")
        self.assertEqual(argv[argv.index("-s") + 1], "workspace-write")
        self.assertIn("sandbox_workspace_write.network_access=true", argv)
        roots_arg = next(part for part in argv if part.startswith(
            "sandbox_workspace_write.writable_roots="))
        roots = json.loads(roots_arg.split("=", 1)[1])
        self.assertEqual(len(roots), len(set(roots)))
        for path in ("/repo-wt", "/repo/output/llm/hand-ext", "/repo/docs/handoffs",
                     "/repo/output/llm", "~/.hybrid-hands", "~/.hybrid-hands/worktrees",
                     "~/.dsh-hand", "~/.codex-hand", "~/.claude"):
            self.assertIn(str(Path(path).expanduser()), roots)
        prompt = build_codex_prompt("hi", "n", Path("/repo/docs/handoffs/n.md"))
        self.assertIn(str(HAND_EXT_BIN), prompt)
        self.assertNotIn(C.HAND_EXT_PLACEHOLDER, prompt)

    def test_worktree_workdir_adds_repo_git_common_dir(self):
        with tempfile.TemporaryDirectory() as d:
            repo, worktree = Path(d) / "repo", Path(d) / "wt"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c",
                            "user.email=t@e", "commit", "--allow-empty", "-qm", "i"],
                           check=True)
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q",
                            str(worktree)], check=True)
            cfg = self._cfg("")
            cfg.repo = repo
            argv = codex_argv(cfg, str(worktree), "hi")
            roots = json.loads(next(part for part in argv if part.startswith(
                "sandbox_workspace_write.writable_roots=")).split("=", 1)[1])
            self.assertIn(str((repo / ".git").resolve()),
                          [str(Path(path).resolve()) for path in roots])

    def test_codex_context_does_not_cap_cumulative_usage(self):
        self.assertIn("model_auto_compact_token_limit=272000", codex_argv(self._cfg(""), "/w", "hi"))
        with tempfile.TemporaryDirectory() as d:
            cfg = SideConfig(Path(d), Path(d)/"h", Path(d)/"wt", 2, 300000, 0,
                             state_dir=Path(d)/"state", codex_home=Path(d))
            rollout = write_rollout(
                Path(d)/"sessions"/"rollout-2026-11-07T00-00-00-a1b2c3.jsonl", Path(d),
                time.time(), {"input_tokens": 400000},
                {"input_tokens": 10000, "cached_input_tokens": 9000, "output_tokens": 100})
            state.save(cfg.state_dir, state.SessionState(
                "n", "u", C.PROVIDER_CODEX, d, "side-n", "side-n-watch", 300000, 0,
                C.STATUS_RUNNING, str(cfg.handoff_dir/"n.md")))
            out = io.StringIO()
            with mock.patch.object(actions.screen, "is_alive", return_value=True), redirect_stdout(out), \
                    mock.patch.object(actions.screen, "screen_names", return_value={"side-n"}):
                self.assertTrue(actions.watch_tick(cfg, "n"))
                actions.ls(cfg, None)
                with mock.patch.object(actions.screen, "quit") as quit_screen:
                    self.assertEqual(actions.stop(cfg, SimpleNamespace(name="n")), 0)
            self.assertEqual(quit_screen.call_args_list, [mock.call("side-n"),
                                                          mock.call("side-n-watch")])
            self.assertEqual(state.load(cfg.state_dir, "n").tokens_used, 400000)
            self.assertRegex(out.getvalue(), r"10100/272000\s+\S")
            self.assertIn("stopped n (context 272000 (tự nén))", out.getvalue())
            self.assertNotIn("/300000 tokens", out.getvalue())

    def test_start_creates_handoff_dir_before_screen(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = SideConfig(Path(d), Path(d)/"missing"/"h", Path(d)/"wt", 2, 300000, 0,
                             state_dir=Path(d)/"state")
            args = build_parser().parse_args(["start", "--name", "n", "--prompt", "hi",
                                              "--provider", C.PROVIDER_CODEX])
            with mock.patch.object(actions.K, "session_cmd", return_value=["screen"]), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    mock.patch.object(actions.subprocess, "run") as run, redirect_stdout(io.StringIO()):
                run.side_effect = lambda *a, **kw: (self.assertTrue(cfg.handoff_dir.is_dir())
                                                   or SimpleNamespace(returncode=0, stdout=""))
                self.assertEqual(actions.start(cfg, args), 0)


class DoneContractTest(unittest.TestCase):
    def test_done_marker_sets_status_done_in_ls_and_watch(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            cfg = SideConfig(repo=tmp, handoff_dir=tmp / "handoffs",
                             worktree_root=tmp / "wt", max_parallel=2,
                             default_max_tokens=1000, watch_interval_s=0,
                             state_dir=tmp / "state", codex_home=tmp / "codex")
            handoff = cfg.handoff_dir / "n.md"
            handoff.parent.mkdir()
            handoff.write_text("## Tóm tắt\n- Kết quả: xong\n")
            handoff.with_suffix(C.DONE_SUFFIX).write_text("")
            started = time.time() - 1
            rollout = write_rollout(
                cfg.codex_home/C.CODEX_SESSIONS_SUBDIR/"2026/11/07/rollout-done.jsonl",
                tmp, started + 1, {"input_tokens": 10})
            state.save(cfg.state_dir, state.SessionState(
                name="n", uuid="u", provider=C.PROVIDER_CODEX, dir=str(tmp),
                screen="side-n", watch_screen="side-n-watch", max_tokens=1000,
                started=started, status=C.STATUS_RUNNING, handoff=str(handoff)))
            out = io.StringIO()
            with mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(out):
                # Watch first: ls also pins, so checking after ls would hide this.
                self.assertEqual(actions.watch(
                    cfg, SimpleNamespace(name="n", interval=None, once=True)), 0)
                self.assertEqual(normalise(state.load(cfg.state_dir, "n").codex_rollout),
                                 normalise(rollout))
                self.assertEqual(actions.ls(cfg, None), 0)
            self.assertIn(C.STATUS_DONE, out.getvalue())
            self.assertEqual(state.load(cfg.state_dir, "n").status, C.STATUS_DONE)


class CodexTrustTest(unittest.TestCase):
    def test_start_trusts_codex_workdir_once(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            screen = tmp / "bin" / "screen"
            screen.parent.mkdir()
            screen.write_text('#!/bin/sh\n[ "$1" = "-dmS" ] && sh -c "$5"\nexit 0\n')
            screen.chmod(0o755)
            cfg = SideConfig(repo=tmp, handoff_dir=tmp / "h", worktree_root=tmp / "wt",
                             max_parallel=1, default_max_tokens=1, watch_interval_s=0,
                             state_dir=tmp / "state", codex_home=tmp / "codex")
            args = SimpleNamespace(
                name="n", resume=False, prompt="x", prompt_file=None, provider=C.PROVIDER_CODEX,
                chrome=None, worktree=False, base=None, max_tokens=None, hours=None, model=None,
                effort=None, dry_run=False, brain="", budget_exempt=False, force_budget=False)
            with mock.patch.dict(os.environ, {"PATH": f"{screen.parent}{os.pathsep}{os.environ['PATH']}"}), \
                    mock.patch.object(actions.K, "watch_cmd", return_value=["true"]), \
                    mock.patch.object(actions.K, "provider_argv",
                                      return_value=(["true"], {})), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(actions.start(cfg, args), 0)
                state.state_path(cfg.state_dir, "n").unlink()
                self.assertEqual(actions.start(cfg, args), 0)
            text = (cfg.codex_home / "config.toml").read_text()
            self.assertEqual(text.count(f'[projects."{tmp}"]'), 1)
            self.assertIn('trust_level = "trusted"', text)


class CodexTokensTest(unittest.TestCase):
    def test_codex_tokens_ignore_cached_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "rollout.jsonl"
            path.write_text(json.dumps({"type": "event_msg", "payload": {
                "type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 304000, "cached_input_tokens": 260000,
                    "output_tokens": 4800}}}}) + "\n")
            self.assertEqual(tokens.codex_tokens(path), 48800)


class RolloutSinceTest(unittest.TestCase):
    def test_older_rollout_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            work, other = tmp/"work", tmp/"other"
            work.mkdir()
            other.mkdir()
            day = tmp / C.CODEX_SESSIONS_SUBDIR / "2026/11/04"
            started = time.time() - 1
            write_rollout(day/"rollout-2026-11-04T00-00-00-old.jsonl", work,
                          started - OLD_AGE_S, {"input_tokens": 9000})
            self.assertIsNone(tokens.codex_rollout(tmp, str(work), started))
            # Filename contains the uuid, but cwd does not match: never counted.
            write_rollout(day/"rollout-2026-11-04T01-00-00-uuid-here.jsonl", other,
                          started + 1, {"input_tokens": 10})
            self.assertIsNone(tokens.codex_rollout(tmp, str(work), started))
            # mtime is not creation time; the session_meta timestamp decides.
            right = write_rollout(day/"rollout-2026-11-04T02-00-00-right.jsonl", work,
                                  started + 2, {"input_tokens": 50})
            past = started - OLD_AGE_S
            os.utime(right, (past, past))
            self.assertEqual(normalise(tokens.codex_rollout(tmp, str(work), started)),
                             normalise(right))


class RolloutPinTest(unittest.TestCase):
    def test_pins_earliest_matching_rollout_and_keeps_it(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            work = {name: tmp/name for name in ("work-a", "work-b", "work-c", "work-d")}
            for path in work.values():
                path.mkdir()
            cfg = SideConfig(tmp, tmp/"handoffs", tmp/"wt", 2, 1000, 0,
                             state_dir=tmp/"state", codex_home=tmp/"codex")
            day = cfg.codex_home / C.CODEX_SESSIONS_SUBDIR / "2026/11/07"
            started = time.time() - 60
            write_rollout(day/"rollout-old.jsonl", work["work-a"], started - OLD_AGE_S,
                          {"input_tokens": 9000})
            write_rollout(day/"rollout-hand.jsonl", work["work-c"], started + 40,
                          {"input_tokens": 5000})
            right_a = write_rollout(day/"rollout-aaaa.jsonl", work["work-a"], started + 2,
                                    {"input_tokens": 50})
            right_b = write_rollout(day/"rollout-bbbb.jsonl", work["work-b"], started + 3,
                                    {"input_tokens": 60})
            for name, workdir in (("n", "work-a"), ("m", "work-b"), ("u", "work-d")):
                state.save(cfg.state_dir, state.SessionState(
                    name, f"uuid-{name}", C.PROVIDER_CODEX, str(work[workdir]),
                    f"side-{name}", f"side-{name}-watch", 1000, started,
                    C.STATUS_RUNNING, str(cfg.handoff_dir/f"{name}.md")))
            with mock.patch.object(actions.screen, "screen_names", return_value={"side-n"}), \
                    mock.patch.object(actions.screen, "is_alive", return_value=True):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertTrue(actions.watch_tick(cfg, "n"))
                    pinned_a = state.load(cfg.state_dir, "n").codex_rollout
                    self.assertEqual(normalise(pinned_a), normalise(right_a))
                    self.assertEqual(state.load(cfg.state_dir, "n").tokens_used, 50)
                    actions.ls(cfg, None)
                self.assertEqual(normalise(state.load(cfg.state_dir, "m").codex_rollout),
                                 normalise(right_b))
                write_rollout(day/"rollout-later.jsonl", work["work-a"], started + 50,
                              {"input_tokens": 700})
                out = io.StringIO()
                with redirect_stdout(out):
                    actions.ls(cfg, None)
                self.assertEqual(state.load(cfg.state_dir, "n").codex_rollout, pinned_a)
                self.assertIn("50/272000", out.getvalue())
                right_a.unlink()
                out = io.StringIO()
                with redirect_stdout(out):
                    actions.ls(cfg, None)
            self.assertEqual(state.load(cfg.state_dir, "n").codex_rollout, pinned_a)
            self.assertRegex(out.getvalue(), r"(?m)^n\s+codex\s+no\s+running\s+alive\s+\?")
            self.assertRegex(out.getvalue(), r"(?m)^u\s+codex\s+no\s+running\s+dead\s+\?")


if __name__ == "__main__":
    unittest.main()
