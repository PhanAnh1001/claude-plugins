"""Soft token cap: keep counting/warning but do not stop when enforce_token_cap=false."""
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

FAKE_SCREEN = """#!/bin/sh
echo "$@" >> "$FAKE_DIR/screen.log"
case "$1" in
  -ls) while read n; do printf '\\t1234.%s\\t(Detached)\\n' "$n"; done < "$FAKE_DIR/alive"; exit 1;;
  -dmS) echo "$2" >> "$FAKE_DIR/alive";;
  -S) grep -vx "${2#*.}" "$FAKE_DIR/alive" > "$FAKE_DIR/alive.new"; mv "$FAKE_DIR/alive.new" "$FAKE_DIR/alive";;
esac
"""
FAKE_FAIL = "#!/bin/sh\necho fake-must-not-run >&2\nexit 99\n"
RULES = "## LUẬT BẮT BUỘC\n- Không đọc .env.\n"


class SoftTokenCapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="side-session-soft-cap-test-"))
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

    # ---- helpers --------------------------------------------------------
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

    def set_token_file(self, st: dict, value: int) -> None:
        path = self.repo / "tokens" / f"{st['uuid']}.tokens"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value))

    def kill_screen(self, name: str) -> None:
        alive = self.tmp / "alive"
        lines = [line for line in alive.read_text().splitlines()
                 if line.strip() and line.strip() != f"side-{name}"]
        alive.write_text("\n".join(lines) + ("\n" if lines else ""))

    def start_ext(self, name: str, max_tokens: int) -> int:
        with mock.patch.object(actions.K, "worktree_cmd", return_value=["true"]):
            code, _ = self.run_cli("start", "--name", name, "--provider", "dsh",
                                   "--worktree", "--prompt", RULES,
                                   "--max-tokens", str(max_tokens))
        return code

    def write_run(self, st: dict, *, status: str = "running") -> None:
        run_dir = self.tmp / "run-1"
        run_dir.mkdir(exist_ok=True)
        run_started = st["started"] + 1
        data = {"run_id": "run-1", "label": f"side:{st['name']}",
                "backend": st["provider"], "status": status,
                "tokens": {"input": 1200, "cached_input": 999, "output": 34},
                "started": run_started, "ended": run_started + 1,
                "run_dir": str(run_dir), "pid": os.getpid()}
        runs = self.machine / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "run-1.json").write_text(json.dumps(data))

    # ---- config ---------------------------------------------------------
    def test_enforce_token_cap_defaults_true(self) -> None:
        self.assertIs(load_config(self.repo).enforce_token_cap, True)

    def test_enforce_token_cap_rejects_non_bool(self) -> None:
        for bad in ("false", 1, None):
            with self.subTest(bad=bad):
                self.configure(enforce_token_cap=bad)
                with self.assertRaises(ValueError) as raised:
                    load_config(self.repo)
                self.assertIn("side_session.enforce_token_cap", str(raised.exception))
                self.assertIn("bool", str(raised.exception))

    # ---- default (hard cap) ---------------------------------------------
    def test_default_still_caps_at_cap(self) -> None:
        self.run_cli("start", "--name", "hard", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "1000")
        st = self.state("hard")
        tdir = self.projects / tokens.project_slug(st["dir"])
        tdir.mkdir(parents=True)
        shutil.copy(FIX / "claude_transcript.jsonl", tdir / f"{st['uuid']}.jsonl")
        code, out = self.run_cli("watch", "--name", "hard", "--once")
        self.assertEqual(code, 0)
        self.assertIn("capped", out)
        self.assertEqual(self.state("hard")["status"], "capped")
        self.assertIn("-S 1234.side-hard -X quit", self.screen_log())

    # ---- soft cap --------------------------------------------------------
    def test_soft_cap_keeps_running_and_warns_once(self) -> None:
        self.configure(enforce_token_cap=False, token_file="tokens/{uuid}.tokens")
        self.run_cli("start", "--name", "soft", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "100")
        st = self.state("soft")
        self.set_token_file(st, 150)
        code, out = self.run_cli("watch", "--name", "soft", "--once")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("over cap"), 1)
        self.assertIn("soft: over cap 150/100 (không dừng: enforce_token_cap=false)", out)
        final = self.state("soft")
        self.assertEqual(final["status"], "running")
        self.assertEqual(final["tokens_used"], 150)
        self.assertNotIn("-S 1234.side-soft -X quit", self.screen_log())

    def test_soft_cap_marks_dead_when_screen_dies(self) -> None:
        self.configure(enforce_token_cap=False, token_file="tokens/{uuid}.tokens")
        self.run_cli("start", "--name", "dead", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "100")
        self.set_token_file(self.state("dead"), 150)
        self.kill_screen("dead")
        self.run_cli("watch", "--name", "dead", "--once")
        self.assertEqual(self.state("dead")["status"], "dead")

    def test_soft_cap_keeps_80_percent_warning(self) -> None:
        self.configure(enforce_token_cap=False, token_file="tokens/{uuid}.tokens")
        self.run_cli("start", "--name", "warn", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "100")
        self.set_token_file(self.state("warn"), 85)
        _, out = self.run_cli("watch", "--name", "warn", "--once")
        self.assertIn("warn: warning 85/100 (>= 80%)", out)
        self.assertEqual(self.state("warn")["status"], "running")

    def test_soft_cap_keeps_daystop(self) -> None:
        self.configure(enforce_token_cap=False)
        self.budget(0)
        self.run_cli("start", "--name", "d", "--provider", "claude", "--prompt", "x")
        self.budget(20)
        code, out = self.run_cli("watch", "--name", "d", "--once")
        self.assertEqual(code, 0)
        self.assertIn("daystop", out)
        self.assertEqual(self.state("d")["status"], "daystop")

    def test_soft_cap_external_provider_keeps_running(self) -> None:
        self.configure(enforce_token_cap=False)
        self.assertEqual(self.start_ext("ext", 100), 0)
        self.write_run(self.state("ext"))
        code, out = self.run_cli("watch", "--name", "ext", "--once")
        self.assertEqual(code, 0)
        self.assertIn("ext: over cap 235/100 (không dừng: enforce_token_cap=false)", out)
        final = self.state("ext")
        self.assertEqual(final["status"], "running")
        self.assertEqual(final["tokens_used"], 235)

    # ---- ls --------------------------------------------------------------
    def test_ls_marks_over_cap_in_both_modes(self) -> None:
        self.configure(token_file="tokens/{uuid}.tokens")
        self.run_cli("start", "--name", "over", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "100")
        self.run_cli("start", "--name", "under", "--provider", "claude",
                     "--prompt", "x", "--max-tokens", "100")
        self.set_token_file(self.state("over"), 150)
        self.set_token_file(self.state("under"), 50)
        _, out = self.run_cli("ls")
        self.assertIn("150/100 !", out)
        under_line = next(line for line in out.splitlines() if line.startswith("under"))
        self.assertIn("50/100", under_line)
        self.assertNotIn("!", under_line)
        self.configure(enforce_token_cap=False)
        _, out = self.run_cli("ls")
        self.assertIn("150/100 !", out)


if __name__ == "__main__":
    unittest.main()
