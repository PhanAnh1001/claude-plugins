"""hand-ext `claude` backend: argv, env, usage parsing, run classification, doctor."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "hand_ext"))
FIX = ROOT / "tests" / "fixtures" / "hand_ext"
FAKE_BIN = str(FIX / "claude_fake.sh")

from codex_harness import Sandbox  # noqa: E402
from hand_ext import day_budget  # noqa: E402
from hand_ext.backends.base import RunSpec, RunState, Status, Usage  # noqa: E402
from hand_ext.backends.claude import (  # noqa: E402
    ClaudeBackend, ClaudeMainBackend, parse_reset,
)
from hand_ext.runner import RunOutcome, child_env  # noqa: E402
from hand_ext_case import HandExtTestCase  # noqa: E402


def _spec(tmp: str, sandbox: str = "workspace-write", **opts) -> RunSpec:
    return RunSpec(prompt="do it", cwd=Path(tmp), run_dir=Path(tmp), model="claude-opus-5-5",
                   effort="medium", sandbox=sandbox, timeout_s=60, max_tokens=None,
                   options={"config_dir": tmp + "/cfg", **opts})


def _run(name: str, exit_code: int = 0, stderr: str = ""):
    backend, state = ClaudeBackend(), RunState(usage=Usage())
    for line in (FIX / name).read_text(encoding="utf-8").splitlines():
        backend.parse_line(line, state)
    with tempfile.TemporaryDirectory() as tmp:
        status = backend.finalize(_spec(tmp), state, exit_code, stderr)
    return status, state


class ArgvTest(HandExtTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        patcher = mock.patch.dict(os.environ, {"HAND_EXT_CLAUDE_BIN": FAKE_BIN})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_argv_and_stdin(self):
        argv, env, stdin = ClaudeBackend().build_command(_spec(self.tmp))
        self.assertEqual(argv[:2], [FAKE_BIN, "-p"])
        for pair in (["--output-format", "stream-json"], ["--model", "claude-opus-5-5"],
                     ["--effort", "medium"], ["--max-turns", "80"],
                     ["--permission-mode", "acceptEdits"]):
            i = argv.index(pair[0])
            self.assertEqual(argv[i:i + 2], pair)
        self.assertIn("--verbose", argv)
        self.assertNotIn("--bare", argv)
        self.assertNotIn("--disallowedTools", argv)
        self.assertEqual(stdin, "do it")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], self.tmp + "/cfg")

    def test_read_only_uses_plan_and_blocks_writes(self):
        argv, _, _ = ClaudeBackend().build_command(_spec(self.tmp, sandbox="read-only"))
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "plan")
        self.assertEqual(argv[argv.index("--disallowedTools") + 1], "Edit,Write,NotebookEdit")

    def test_append_system_prompt_file(self):
        argv, _, _ = ClaudeBackend().build_command(
            _spec(self.tmp, append_system_prompt="be a hand"))
        path = Path(argv[argv.index("--append-system-prompt-file") + 1])
        self.assertEqual(path.read_text(encoding="utf-8"), "be a hand")

    def test_blocked_env_removed(self):
        blocked = {k: "x" for k in ClaudeBackend.BLOCKED_ENV}
        with mock.patch.dict(os.environ, blocked):
            env = ClaudeBackend()._base_env({"config_dir": self.tmp})
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
                    "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK"):
            self.assertNotIn(key, env)
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], self.tmp)


class ClassifyTest(HandExtTestCase):
    def test_success_usage_from_model_usage(self):
        status, state = _run("claude_success.jsonl")
        self.assertEqual(status, Status.OK)
        self.assertEqual(state.final_text, "DONE")
        self.assertEqual((state.usage.input, state.usage.cached_input, state.usage.output),
                         (1310, 1000, 55))

    def test_max_turns_is_capped(self):
        self.assertEqual(_run("claude_max_turns.jsonl", exit_code=1)[0], Status.CAPPED)

    def test_quota(self):
        status, state = _run("claude_quota.jsonl", exit_code=1)
        self.assertEqual(status, Status.QUOTA)
        self.assertTrue(state.quota.exhausted)
        self.assertEqual(state.quota.window, "session")
        self.assertTrue(state.quota.resets_at.endswith("Z"))

    def test_not_logged_in(self):
        self.assertEqual(_run("claude_not_logged_in.jsonl", exit_code=1)[0],
                         Status.NOT_LOGGED_IN)

    def test_crash_is_failed(self):
        status, state = ClaudeBackend(), RunState(usage=Usage())
        with tempfile.TemporaryDirectory() as tmp:
            result = status.finalize(_spec(tmp), state, 2, "boom")
        self.assertEqual(result, Status.FAILED)

    def test_parse_reset(self):
        now = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)  # Wednesday
        self.assertEqual(parse_reset("3:45pm", now), "2026-11-04T15:45:00Z")
        self.assertEqual(parse_reset("Mon 12:00am", now), "2026-11-09T00:00:00Z")
        self.assertIsNone(parse_reset("soon", now))


class DoctorTest(HandExtTestCase):
    def _doctor(self, logged_in: bool):
        tmp = tempfile.mkdtemp()
        env = {"HAND_EXT_CLAUDE_BIN": FAKE_BIN, "FAKE_CLAUDE_LOGGED_IN": "1" if logged_in else "0"}
        with mock.patch.dict(os.environ, env):
            return {c.name: c for c in ClaudeBackend().doctor({"config_dir": tmp})}

    def test_logged_in_without_leaking_secrets(self):
        checks = self._doctor(True)
        self.assertTrue(checks["installed"].ok)
        self.assertTrue(checks["login"].ok)
        text = " ".join(c.detail for c in checks.values())
        self.assertNotIn("secret-hand", text)
        self.assertNotIn("SECRET-ORG", text)

    def test_not_logged_in(self):
        self.assertFalse(self._doctor(False)["login"].ok)

    def test_main_config_dir_flagged(self):
        with mock.patch.dict(os.environ, {"HAND_EXT_CLAUDE_BIN": FAKE_BIN}):
            checks = {c.name: c for c in ClaudeBackend().doctor({"config_dir": "~/.claude"})}
        self.assertFalse(checks["config_dir"].ok)

    def test_setup_creates_dir(self):
        tmp = tempfile.mkdtemp() + "/new"
        lines = ClaudeBackend().setup({"config_dir": tmp})
        self.assertTrue(Path(tmp).is_dir())
        self.assertIn("/login", "\n".join(lines))


class MainBackendTest(HandExtTestCase):
    def test_main_plan_allowed_for_claude_main_only(self):
        tmp = tempfile.mkdtemp()
        (Path(tmp) / ".claude").mkdir()
        env = {"HAND_EXT_CLAUDE_BIN": FAKE_BIN, "FAKE_CLAUDE_LOGGED_IN": "1", "HOME": tmp}
        with mock.patch.dict(os.environ, env):
            main = {c.name: c for c in ClaudeMainBackend().doctor({"config_dir": "~/.claude"})}
            hand = {c.name: c for c in ClaudeBackend().doctor({"config_dir": "~/.claude"})}
            spec = _spec(tmp, config_dir="~/.claude")
            spec.model, spec.effort = "", ""
            argv, env_add, _ = ClaudeMainBackend().build_command(spec)
        self.assertTrue(main["config_dir"].ok)
        self.assertTrue(main["login"].ok)
        self.assertFalse(hand["config_dir"].ok)
        self.assertNotIn("CLAUDE_CONFIG_DIR", env_add)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5-5")
        self.assertEqual(argv[argv.index("--effort") + 1], "low")

    def test_main_uses_custom_config_dir_without_inheriting_parent(self):
        tmp = tempfile.mkdtemp()
        main_cfg = tmp + "/main-cfg"
        env = {"HAND_EXT_CLAUDE_BIN": FAKE_BIN, "CLAUDE_CONFIG_DIR": "/parent/cfg"}
        with mock.patch.dict(os.environ, env):
            _, env_add, _ = ClaudeMainBackend().build_command(
                _spec(tmp, config_dir=main_cfg))
            doctor_env = ClaudeMainBackend()._base_env({"config_dir": main_cfg})
            _, hand_env, _ = ClaudeBackend().build_command(_spec(tmp, config_dir=main_cfg))
        for kept in (env_add, child_env(ClaudeMainBackend(), env_add), doctor_env):
            self.assertEqual(kept["CLAUDE_CONFIG_DIR"], main_cfg)
        self.assertEqual(hand_env["CLAUDE_CONFIG_DIR"], main_cfg)


class DayBudgetTest(HandExtTestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="claude-home-"))
        (self.home / day_budget.USD_PER_PCT_PIN).write_text("1.0\n", encoding="utf-8")
        self.sb = Sandbox(order=["claude-main"], extra={"backends": {
            "claude-main": {"config_dir": str(self.home), "max_day_pct": 5}}})
        self.addCleanup(self.sb.close)
        self.outcome = RunOutcome(Status.OK, 0, RunState(usage=Usage()), 0.0)

    def _run(self, usd):
        with mock.patch.object(day_budget, "machine_usd", return_value=usd), \
                mock.patch("hand_ext.run_cmd.run_backend",
                           return_value=self.outcome) as run:
            code, _, err = self.sb.cli("run", "--brief", str(self.sb.brief),
                                       "--backend", "claude-main", "--isolation", "none")
        return code, err, run

    def test_day_cap_blocks_at_threshold_and_allows_below(self):
        code, err, run = self._run(5.0)
        self.assertEqual(code, 7, err)
        self.assertIn("máy này đã dùng 5.0% Claude hôm nay (ngưỡng 5%)", err)
        self.assertIn("ghi yêu cầu vào bàn giao để Opus quyết", err)
        run.assert_not_called()
        code, _, run = self._run(4.0)
        self.assertEqual(code, 0)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
