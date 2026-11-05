"""side-session: token_file from the status line and `start --resume` for Claude."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PL = ROOT / "plugins" / "hybrid-hands"
FIX = ROOT / "tests" / "fixtures" / "side_session"
sys.path.insert(0, str(PL / "lib"))

from side_session import actions, cli, constants as C, tokens  # noqa: E402
from side_session.config import load_config  # noqa: E402

FAKE_SCREEN = """#!/bin/sh
echo "$@" >> "$FAKE_DIR/screen.log"
case "$1" in
  -ls) while read n; do printf '\\t1234.%s\\t(Detached)\\n' "$n"; done < "$FAKE_DIR/alive"; exit 1;;
  -dmS) echo "$2" >> "$FAKE_DIR/alive";;
  -S) grep -vx "${2#*.}" "$FAKE_DIR/alive" > "$FAKE_DIR/alive.new"; mv "$FAKE_DIR/alive.new" "$FAKE_DIR/alive";;
esac
"""
FAKE_FAIL = "#!/bin/sh\necho fake-must-not-run >&2\nexit 99\n"
RESUME_PROMPT = ("Phiên này được mở lại sau khi bị dừng. Đọc lại việc đang dở, "
                 "không làm lại bước đã xong, rồi làm tiếp đến hết theo yêu cầu ban đầu.")


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="side-session-resume-test-"))
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
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ.pop("CLAUDE_CODE_CHILD_SESSION", None)
        self._cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def configure(self, **side) -> None:
        path = self.repo / ".claude" / "hybrid-hands.json"
        path.parent.mkdir(exist_ok=True)
        data = json.loads(path.read_text()) if path.is_file() else {}
        data.setdefault("side_session", {}).update(side)
        path.write_text(json.dumps(data))

    def state(self, name: str) -> dict:
        return json.loads((self.repo / "output/llm/side-sessions" / f"{name}.json").read_text())

    def write_state(self, name: str, **overrides) -> dict:
        st = {"name": name, "uuid": "uuid-x", "provider": C.PROVIDER_CLAUDE,
              "dir": str(self.repo), "screen": f"side-{name}",
              "watch_screen": f"side-{name}-watch", "max_tokens": 1000,
              "started": 1.0, "status": C.STATUS_STOPPED,
              "handoff": str(self.repo / "docs" / f"{name}.md")}
        st.update(overrides)
        path = self.repo / "output/llm/side-sessions" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(st))
        return st

    def screen_log(self) -> str:
        log = self.tmp / "screen.log"
        return log.read_text() if log.exists() else ""

    def transcript(self, st: dict) -> None:
        tdir = self.projects / tokens.project_slug(st["dir"])
        tdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / "claude_transcript.jsonl", tdir / f"{st['uuid']}.jsonl")

    def start_claude(self, name: str = "r", *args: str) -> tuple[int, str]:
        return self.run_cli("start", "--name", name, "--prompt", "làm việc", *args)

    def stop(self, name: str = "r") -> None:
        code, _ = self.run_cli("stop", name)
        self.assertEqual(code, 0)


class TokenFileTest(_Base):
    def test_default_is_empty_and_relative_path_is_resolved(self) -> None:
        self.assertEqual(load_config(self.repo).token_file, "")
        self.configure(token_file="sessions/ops/runs/{uuid}.tokens")
        self.assertEqual(load_config(self.repo).token_file,
                         str((self.repo / "sessions/ops/runs/{uuid}.tokens").resolve()))

    def test_token_file_value_is_used_for_claude(self) -> None:
        self.configure(token_file="runs/{uuid}.tokens")
        path = self.repo / "runs" / "u-1.tokens"
        path.parent.mkdir()
        path.write_text("445000\n")
        st = SimpleNamespace(provider=C.PROVIDER_CLAUDE, uuid="u-1", dir=str(self.repo),
                             started=0.0)
        self.assertEqual(actions.count_tokens(load_config(self.repo), st), 445000)

    def test_missing_or_invalid_token_file_is_zero_without_transcript_fallback(self) -> None:
        self.configure(token_file="runs/{uuid}.tokens")
        st = SimpleNamespace(provider=C.PROVIDER_CLAUDE, uuid="u-2", dir=str(self.repo),
                             started=0.0)
        self.transcript({"dir": st.dir, "uuid": st.uuid})  # transcript would say 1615
        cfg = load_config(self.repo)
        path = self.repo / "runs" / "u-2.tokens"
        self.assertEqual(actions.count_tokens(cfg, st), 0)
        path.parent.mkdir(exist_ok=True)
        for content in ("abc\n", "-1\n", "1.5\n", ""):
            path.write_text(content)
            self.assertEqual(actions.count_tokens(cfg, st), 0, content)

    def test_unset_token_file_keeps_transcript_count(self) -> None:
        st = SimpleNamespace(provider=C.PROVIDER_CLAUDE, uuid="u-3", dir=str(self.repo),
                             started=0.0)
        self.transcript({"dir": st.dir, "uuid": st.uuid})
        self.assertEqual(actions.count_tokens(load_config(self.repo), st), 1615)

    def test_token_file_does_not_change_codex_or_external_providers(self) -> None:
        self.configure(token_file="runs/{uuid}.tokens")
        cfg = load_config(self.repo)
        codex = SimpleNamespace(provider=C.PROVIDER_CODEX, uuid="c-1", dir=str(self.repo),
                                started=0.0)
        self.transcript({"dir": codex.dir, "uuid": codex.uuid})
        with mock.patch.object(actions.tokens, "codex_rollout", return_value=Path("/x")), \
                mock.patch.object(actions.tokens, "codex_tokens", return_value=42):
            self.assertEqual(actions.count_tokens(cfg, codex), 42)
        for provider in C.EXTERNAL_PROVIDERS:
            st = SimpleNamespace(provider=provider, uuid="e-1", dir=str(self.repo), started=0.0)
            run = object()
            with mock.patch.object(actions.external, "run_for", return_value=run), \
                    mock.patch.object(actions.external, "tokens_used", return_value=7) as used:
                self.assertEqual(actions.count_tokens(cfg, st), 7)
                used.assert_called_once_with(run)

    def test_config_wrong_type_raises_value_error(self) -> None:
        self.configure(token_file=123)
        with self.assertRaisesRegex(ValueError, "token_file.*chuỗi"):
            load_config(self.repo)

    def test_watch_caps_from_token_file(self) -> None:
        self.configure(token_file="runs/{uuid}.tokens")
        code, _ = self.start_claude("tf", "--max-tokens", "100")
        self.assertEqual(code, 0)
        st = self.state("tf")
        path = self.repo / "runs" / f"{st['uuid']}.tokens"
        path.parent.mkdir()
        path.write_text("150\n")
        code, out = self.run_cli("watch", "--name", "tf", "--once")
        self.assertEqual(code, 0)
        self.assertIn("capped at 150/100", out)
        self.assertEqual(self.state("tf")["status"], C.STATUS_CAPPED)
        self.assertEqual(self.state("tf")["tokens_used"], 150)


class ResumeTest(_Base):
    def stopped_session(self, name: str = "r", *args: str) -> dict:
        code, _ = self.start_claude(name, *args)
        self.assertEqual(code, 0)
        self.stop(name)
        return self.state(name)

    def test_resume_argv_preserves_state_and_updates_flags(self) -> None:
        self.configure(status_line_cmd="tools/tap.sh")
        with mock.patch.object(actions.K, "worktree_cmd", return_value=["true"]):
            old = self.stopped_session("r", "--chrome", "--worktree")
        self.assertTrue(old["worktree"])
        self.assertTrue(old["chrome"])
        old["parent_session"] = "brain-old"
        old["tokens_used"] = 99
        old["started"] = 1.0
        (self.repo / "output/llm/side-sessions/r.json").write_text(json.dumps(old))
        before = time.time()

        code, out = self.run_cli("start", "--name", "r", "--resume", "--dry-run",
                                 "--max-tokens", "12345", "--no-chrome")
        self.assertEqual(code, 0)
        self.assertIn(f"claude --resume {old['uuid']} -n r", out)
        self.assertNotIn("--session-id", out)
        self.assertIn(" --no-chrome ", f" {out} ")
        self.assertIn("--settings", out)
        self.assertIn(str((self.repo / "tools/tap.sh").resolve()), out)
        self.assertIn("max_tokens=12345", out)
        self.assertIn(RESUME_PROMPT, out)
        self.assertNotIn("Luật bàn giao cho phiên phụ", out)
        self.assertIn("screen -dmS side-r", out)
        self.assertIn("side-r-watch", out)
        self.assertEqual(self.state("r")["status"], C.STATUS_STOPPED)  # dry-run saves nothing

        code, _ = self.run_cli("start", "--name", "r", "--resume",
                               "--max-tokens", "12345", "--no-chrome")
        self.assertEqual(code, 0)
        new = self.state("r")
        self.assertEqual(new["uuid"], old["uuid"])
        self.assertEqual(new["dir"], old["dir"])
        self.assertEqual(new["handoff"], old["handoff"])
        self.assertEqual(new["worktree"], old["worktree"])
        self.assertEqual(new["parent_session"], "brain-old")
        self.assertEqual(new["max_tokens"], 12345)
        self.assertFalse(new["chrome"])
        self.assertEqual(new["status"], C.STATUS_RUNNING)
        self.assertEqual(new["tokens_used"], 0)
        self.assertGreaterEqual(new["started"], before)
        log = self.screen_log()
        self.assertIn(f"claude --resume {old['uuid']} -n r", log)
        self.assertIn("unset CLAUDE_CODE_CHILD_SESSION;", log)
        self.assertIn("side-r-watch", log)
        self.assertNotIn("worktree add", log)

    def test_resume_keeps_old_cap_and_chrome_when_flags_absent(self) -> None:
        self.stopped_session("keep", "--chrome", "--max-tokens", "777")
        code, out = self.run_cli("start", "--name", "keep", "--resume", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("max_tokens=777", out)
        self.assertIn(" --chrome ", f" {out} ")
        self.assertNotIn("--no-chrome", out)

    def test_resume_updates_parent_session_from_env(self) -> None:
        self.stopped_session("p")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "brain-new"
        code, _ = self.run_cli("start", "--name", "p", "--resume")
        self.assertEqual(code, 0)
        self.assertEqual(self.state("p")["parent_session"], "brain-new")

    def test_resume_prompt_file_is_wrapped_with_handoff_rules(self) -> None:
        old = self.stopped_session("f")
        prompt = self.tmp / "resume.md"
        prompt.write_text("Việc mới cần làm tiếp")
        code, out = self.run_cli("start", "--name", "f", "--resume",
                                 "--prompt-file", str(prompt), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Việc mới cần làm tiếp", out)
        self.assertNotIn(RESUME_PROMPT, out)
        self.assertIn("Luật bàn giao cho phiên phụ", out)
        self.assertIn(old["handoff"], out)

    def test_resume_refused_while_screen_alive(self) -> None:
        code, _ = self.start_claude("live")
        self.assertEqual(code, 0)
        code, out = self.run_cli("start", "--name", "live", "--resume")
        self.assertEqual(code, 2)
        self.assertIn("live", out)
        self.assertEqual(self.screen_log().count("-dmS side-live "), 1)

    def test_resume_refused_without_state(self) -> None:
        code, out = self.run_cli("start", "--name", "missing", "--resume")
        self.assertEqual(code, 2)
        self.assertIn("missing", out)

    def test_resume_refused_for_non_claude_state(self) -> None:
        self.write_state("cx", provider=C.PROVIDER_CODEX)
        code, out = self.run_cli("start", "--name", "cx", "--resume")
        self.assertEqual(code, 2)
        self.assertIn(C.PROVIDER_CLAUDE, out)

    def test_resume_refused_with_other_provider_flag(self) -> None:
        self.stopped_session("pflag")
        code, out = self.run_cli("start", "--name", "pflag", "--resume",
                                 "--provider", C.PROVIDER_CODEX)
        self.assertEqual(code, 2)
        self.assertIn(C.PROVIDER_CLAUDE, out)

    def test_resume_refused_with_worktree_or_base(self) -> None:
        self.stopped_session("wt")
        code, out = self.run_cli("start", "--name", "wt", "--resume", "--worktree")
        self.assertEqual(code, 2)
        self.assertIn("worktree", out)
        code, out = self.run_cli("start", "--name", "wt", "--resume", "--base", "main")
        self.assertEqual(code, 2)
        self.assertIn("base", out)
        self.assertEqual(self.state("wt")["status"], C.STATUS_STOPPED)

    def test_resume_budget_refusal_exit_4_unless_exempt_or_forced(self) -> None:
        script = self.repo / "budget.sh"
        script.write_text("#!/bin/sh\necho budget-says-no\nexit 3\n")
        script.chmod(0o755)
        self.configure(budget_check_cmd=["budget.sh"])
        # Create the old state without the guard, then turn it on for the resume.
        self.configure(budget_check_cmd=[])
        self.stopped_session("b")
        self.configure(budget_check_cmd=["budget.sh"])

        code, out = self.run_cli("start", "--name", "b", "--resume")
        self.assertEqual(code, 4)
        self.assertIn("budget-says-no", out)
        self.assertEqual(self.state("b")["status"], C.STATUS_STOPPED)
        self.assertEqual(self.screen_log().count("-dmS side-b "), 1)

        code, _ = self.run_cli("start", "--name", "b", "--resume", "--force-budget")
        self.assertEqual(code, 0)
        self.assertEqual(self.state("b")["status"], C.STATUS_RUNNING)
        self.assertFalse(self.state("b")["budget_exempt"])
        self.stop("b")

        code, _ = self.run_cli("start", "--name", "b", "--resume", "--budget-exempt")
        self.assertEqual(code, 0)
        self.assertTrue(self.state("b")["budget_exempt"])


if __name__ == "__main__":
    unittest.main()
