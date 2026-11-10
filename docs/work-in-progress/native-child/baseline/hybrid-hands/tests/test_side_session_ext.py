"""side-session v2: Chrome, parent session, day budget, external dsh hands."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PL = ROOT / "plugins" / "hybrid-hands"
sys.path.insert(0, str(PL / "lib"))

from side_session import actions, cli  # noqa: E402

FAKE_SCREEN = """#!/bin/sh
echo "$@" >> "$FAKE_DIR/screen.log"
case "$1" in
  -ls) while read n; do printf '\\t1234.%s\\t(Detached)\\n' "$n"; done < "$FAKE_DIR/alive"; exit 1;;
  -dmS) echo "$2" >> "$FAKE_DIR/alive";;
  -S) grep -vx "$2" "$FAKE_DIR/alive" > "$FAKE_DIR/alive.new"; mv "$FAKE_DIR/alive.new" "$FAKE_DIR/alive";;
esac
"""
FAKE_FAIL = "#!/bin/sh\necho fake-must-not-run >&2\nexit 99\n"
RULES = "## LUẬT BẮT BUỘC\n- Không đọc .env.\n"


class SideSessionExtTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="side-session-ext-test-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        for name, body in (("screen", FAKE_SCREEN), ("claude", FAKE_FAIL),
                           ("codex", FAKE_FAIL)):
            (bindir / name).write_text(body)
            (bindir / name).chmod(0o755)
        (self.tmp / "alive").write_text("")
        self._env = dict(os.environ)
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_DIR"] = str(self.tmp)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ.pop("CLAUDE_CODE_CHILD_SESSION", None)
        self._cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp)

    # ---- helpers --------------------------------------------------------
    def run_cli(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def start(self, *args: str, name: str = "s", prompt: str = "x") -> tuple[int, str]:
        provider = [] if "--provider" in args else ["--provider", "claude"]
        return self.run_cli("start", "--name", name, "--prompt", prompt, *provider, *args)

    def configure(self, **side) -> None:
        path = self.repo / ".claude" / "hybrid-hands.json"
        path.parent.mkdir(exist_ok=True)
        data = json.loads(path.read_text()) if path.is_file() else {}
        data.setdefault("side_session", {}).update(side)
        path.write_text(json.dumps(data))

    def budget(self, code: int, text: str = "budget says no") -> None:
        script = self.repo / "budget.sh"
        script.write_text(f"#!/bin/sh\necho {text!r}\nexit {code}\n")
        script.chmod(0o755)
        self.configure(budget_check_cmd=["budget.sh"])

    def state(self, name: str) -> dict:
        return json.loads((self.repo / "output/llm/side-sessions" / f"{name}.json").read_text())

    def screen_log(self) -> str:
        log = self.tmp / "screen.log"
        return log.read_text() if log.exists() else ""

    # ---- start: chrome, parent, budget ---------------------------------
    def test_chrome_replaces_no_chrome_and_sets_state(self) -> None:
        code, out = self.start("--chrome", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn(" --chrome ", f" {out} ")
        self.assertNotIn("--no-chrome", out)
        code, _ = self.start("--chrome")
        self.assertEqual(code, 0)
        self.assertTrue(self.state("s")["chrome"])
        self.assertIn(" --chrome ", f" {self.screen_log()} ")
        self.assertNotIn("--no-chrome", self.screen_log())

    def test_no_chrome_overrides_configured_chrome(self) -> None:
        self.configure(claude_args=["--chrome"])
        code, out = self.start("--no-chrome", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn(" --no-chrome ", f" {out} ")
        self.assertNotIn(" --chrome ", f" {out} ")

    def test_chrome_rejected_for_other_providers(self) -> None:
        for provider in ("codex", "dsh"):
            code, out = self.start("--provider", provider, "--chrome", "--worktree",
                                   "--prompt", RULES, name=provider)
            self.assertEqual(code, 2, provider)
            self.assertIn("chrome", out.lower())
        self.assertFalse((self.repo / "output").exists())
        self.assertEqual(self.screen_log().count("-dmS"), 0)

    def test_parent_session_from_env(self) -> None:
        os.environ["CLAUDE_CODE_SESSION_ID"] = "brain-abc"
        self.start(name="p1")
        self.assertEqual(self.state("p1")["parent_session"], "brain-abc")
        os.environ.pop("CLAUDE_CODE_SESSION_ID")
        self.start(name="p2")
        self.assertEqual(self.state("p2")["parent_session"], "")

    def test_budget_refuses_unless_exempt_or_forced(self) -> None:
        self.budget(3, "HẾT HẠN MỨC HÔM NAY")
        code, out = self.start(name="b1")
        self.assertEqual(code, 4)
        self.assertIn("HẾT HẠN MỨC HÔM NAY", out)
        self.assertFalse((self.repo / "output").exists())
        code, _ = self.start("--budget-exempt", name="b2")
        self.assertEqual(code, 0)
        self.assertTrue(self.state("b2")["budget_exempt"])
        code, _ = self.start("--force-budget", name="b3")
        self.assertEqual(code, 0)
        self.assertFalse(self.state("b3")["budget_exempt"])

    def test_budget_unrunnable_counts_as_failure(self) -> None:
        self.configure(budget_check_cmd=["no-such-budget.sh"])
        code, _ = self.start(name="missing")
        self.assertEqual(code, 4)
        self.assertFalse((self.repo / "output").exists())

    def test_watch_budget_code_20_daystops_unless_exempt(self) -> None:
        self.budget(0)
        self.start(name="d1")
        self.budget(20)
        code, out = self.run_cli("watch", "--name", "d1", "--once")
        self.assertEqual(code, 0)
        self.assertIn("daystop", out)
        self.assertEqual(self.state("d1")["status"], "daystop")
        self.start("--budget-exempt", name="d2")
        code, _ = self.run_cli("watch", "--name", "d2", "--once")
        self.assertEqual(code, 0)
        self.assertEqual(self.state("d2")["status"], "running")

    # ---- external providers --------------------------------------------
    def test_dsh_needs_worktree_and_rules(self) -> None:
        code, out = self.start("--provider", "dsh", "--prompt", RULES)
        self.assertEqual(code, 2)
        self.assertIn("worktree", out)
        code, out = self.start("--provider", "dsh", "--worktree", "--prompt", "hello")
        self.assertEqual(code, 2)
        self.assertIn("LUẬT BẮT BUỘC", out)
        self.assertFalse((self.repo / "output").exists())

    def test_dsh_dry_run_builds_hand_ext_argv(self) -> None:
        code, out = self.start("--provider", "dsh", "--worktree", "--prompt", RULES,
                               "--dry-run", name="dsh1")
        self.assertEqual(code, 0)
        self.assertIn("hand-ext run --backend dsh", out)
        self.assertIn("--brief ", out)
        self.assertIn("dsh1.prompt.md", out)
        self.assertIn("--label side:dsh1", out)
        self.assertIn("repo-wt/dsh1", out)
        self.assertNotIn("--max-tokens", out)
        self.assertNotIn("--chrome", out)
        self.assertFalse((self.repo / "output").exists())

    def test_status_line_cmd_resolved_from_repo_for_claude_only(self) -> None:
        self.configure(status_line_cmd="tools/tap.sh")
        code, out = self.start("--dry-run", name="sl1")
        self.assertEqual(code, 0)
        self.assertIn("--settings", out)
        self.assertIn(str(self.repo.resolve() / "tools" / "tap.sh"), out)
        code, out = self.start("--provider", "dsh", "--worktree", "--prompt", RULES,
                               "--dry-run", name="sl2")
        self.assertEqual(code, 0)
        self.assertNotIn("--settings", out)

    def test_dsh_hours_become_hand_ext_timeout(self) -> None:
        code, out = self.start("--provider", "dsh", "--worktree", "--prompt", RULES,
                               "--hours", "2", "--dry-run", name="dsh2")
        self.assertEqual(code, 0)
        self.assertIn("--timeout-min 120", out)
        self.assertNotIn("--max-tokens", out)

    def test_dsh_start_writes_prompt_state_and_screen_argv(self) -> None:
        with mock.patch.object(actions.K, "worktree_cmd", return_value=["true"]):
            code, _ = self.start("--provider", "dsh", "--worktree", "--prompt", RULES,
                                 name="x")
        self.assertEqual(code, 0)
        st = self.state("x")
        self.assertEqual(st["provider"], "dsh")
        self.assertFalse(st["chrome"])
        self.assertEqual(uuid.UUID(st["uuid"]).version, 4)
        prompt = self.repo / "output/llm/side-sessions/x.prompt.md"
        self.assertIn("LUẬT BẮT BUỘC", prompt.read_text())
        log = self.screen_log()
        self.assertIn("bin/hand-ext run --backend dsh", log)
        self.assertIn("--label side:x", log)
        self.assertIn("--brief " + str(prompt.resolve()), log)

    def test_ls_shows_provider_and_chrome(self) -> None:
        self.start("--chrome", name="a")
        self.start("--no-chrome", name="b")
        _, out = self.run_cli("ls")
        self.assertIn("CHROME", out)
        rows = {line.split()[0]: line.split() for line in out.splitlines()
                if line.split() and line.split()[0] in ("a", "b")}
        self.assertEqual(rows["a"][1:3], ["claude", "yes"])
        self.assertEqual(rows["b"][1:3], ["claude", "no"])

    def test_child_session_env_is_removed_from_child(self) -> None:
        self.start(name="env")
        log = self.screen_log()
        self.assertIn("unset CLAUDE_CODE_CHILD_SESSION;", log)
        self.assertNotIn("CLAUDE_CODE_CHILD_SESSION=", log)

    def test_old_state_without_new_fields_still_loads(self) -> None:
        state_dir = self.repo / "output/llm/side-sessions"
        state_dir.mkdir(parents=True)
        old = {"name": "old", "uuid": "u", "provider": "claude", "dir": str(self.repo),
               "screen": "side-old", "watch_screen": "side-old-watch", "max_tokens": 10,
               "started": 1.0, "status": "stopped",
               "handoff": str(self.repo / "docs/old.md")}
        (state_dir / "old.json").write_text(json.dumps(old))
        code, out = self.run_cli("ls")
        self.assertEqual(code, 0)
        self.assertIn("old", out)


if __name__ == "__main__":
    unittest.main()
