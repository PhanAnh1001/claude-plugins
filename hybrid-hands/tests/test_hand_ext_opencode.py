"""hand-ext opencode backend: argv, env blocking, usage parsing, classification, doctor."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext.backends.base import RunSpec, RunState, Status, Usage  # noqa: E402
from hand_ext.backends import opencode as oc  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "hand_ext"
FAKE_BIN = FIXTURES / "opencode_fake.sh"
BIN_ENV = "HAND_EXT_OPENCODE_BIN"
TIMEOUT_S = 60


def _spec(run_dir: Path, model: str = oc.DEFAULT_MODEL, effort: str = "max",
          sandbox: str = "workspace-write") -> RunSpec:
    return RunSpec(prompt="brief body", cwd=Path("/repo"), run_dir=run_dir, model=model,
                   effort=effort, sandbox=sandbox, timeout_s=TIMEOUT_S, max_tokens=None,
                   options={})


def _feed(name: str) -> RunState:
    state = RunState(usage=Usage())
    backend = oc.OpencodeBackend()
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        backend.parse_line(line, state)
    return state


class BuildCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)
        self.backend = oc.OpencodeBackend()
        patcher = mock.patch.dict(os.environ, {BIN_ENV: "/fake/opencode"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_argv_and_prompt_file(self):
        argv, env, stdin = self.backend.build_command(_spec(self.run_dir))
        prompt = self.run_dir / oc.PROMPT_FILE
        self.assertEqual(argv[:2], ["/fake/opencode", "run"])
        for flag, value in (("--model", oc.DEFAULT_MODEL), ("--variant", "max"),
                            ("--format", "json"), ("--dir", "/repo"),
                            ("--agent", oc.AGENT_WRITE), ("-f", str(prompt))):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn("--pure", argv)
        self.assertIn("--auto", argv)
        self.assertEqual(argv[-1], oc.SHORT_MESSAGE)
        self.assertEqual(prompt.read_text(encoding="utf-8"), "brief body")
        self.assertEqual(env, {oc.CONFIG_ENV: str(oc.DEFAULT_CONFIG)})
        self.assertIsNone(stdin)

    def test_effort_outside_variants_falls_back(self):
        argv, _, _ = self.backend.build_command(_spec(self.run_dir, effort="medium"))
        self.assertEqual(argv[argv.index("--variant") + 1], oc.DEFAULT_VARIANT)
        argv, _, _ = self.backend.build_command(_spec(self.run_dir, effort="low"))
        self.assertEqual(argv[argv.index("--variant") + 1], "low")

    def test_read_only_uses_readonly_agent(self):
        argv, _, _ = self.backend.build_command(_spec(self.run_dir, sandbox="read-only"))
        self.assertEqual(argv[argv.index("--agent") + 1], oc.AGENT_READONLY)

    def test_rejects_non_subscription_model(self):
        for model in ("opencode/deepseek-v4.1-flash-free", "openai/gpt-5", "deepseek/x"):
            with self.assertRaises(ValueError):
                self.backend.build_command(_spec(self.run_dir, model=model))

    def test_blocked_env_covers_paid_keys(self):
        for key in ("OPENCODE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                    "GEMINI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY",
                    "OPENROUTER_API_KEY"):
            self.assertIn(key, oc.OpencodeBackend.BLOCKED_ENV)

    def test_config_template_exists_and_denies_env(self):
        text = oc.DEFAULT_CONFIG.read_text(encoding="utf-8")
        self.assertIn('"*.env": "deny"', text)
        self.assertIn('"external_directory": "deny"', text)
        self.assertIn('"share": "disabled"', text)
        self.assertIn('"%s"' % oc.AGENT_READONLY, text)


class ParseAndFinalizeTest(unittest.TestCase):
    def setUp(self):
        self.spec = _spec(Path(tempfile.gettempdir()))
        self.backend = oc.OpencodeBackend()

    def test_success_usage_summed(self):
        state = _feed("opencode_success.jsonl")
        self.assertEqual(state.usage.input, 1000 + 3000 + 500 + 4000 + 10)
        self.assertEqual(state.usage.cached_input, 7000)
        self.assertEqual(state.usage.output, 50 + 200 + 100)
        self.assertAlmostEqual(state.extra["cost_usd_reference"], 0.003)
        self.assertIn("Kết quả", state.final_text)
        self.assertEqual(self.backend.finalize(self.spec, state, 0, ""), Status.OK)

    def test_quota(self):
        state = _feed("opencode_quota.jsonl")
        self.assertEqual(self.backend.finalize(self.spec, state, 1, ""), Status.QUOTA)

    def test_quota_from_stderr_only(self):
        state = RunState(usage=Usage())
        status = self.backend.finalize(self.spec, state, 1, "GoUsageLimitError weekly")
        self.assertEqual(status, Status.QUOTA)

    def test_not_logged_in(self):
        state = _feed("opencode_not_logged_in.jsonl")
        self.assertEqual(self.backend.finalize(self.spec, state, 1, ""), Status.NOT_LOGGED_IN)

    def test_plain_failure_and_garbage_lines(self):
        state = RunState(usage=Usage())
        self.backend.parse_line("not json", state)
        self.backend.parse_line("{broken", state)
        self.assertEqual(self.backend.finalize(self.spec, state, 2, "boom"), Status.FAILED)


class DoctorTest(unittest.TestCase):
    def test_doctor_with_fake_bin(self):
        with mock.patch.dict(os.environ, {BIN_ENV: str(FAKE_BIN)}):
            checks = {c.name: c for c in oc.OpencodeBackend().doctor({})}
        self.assertTrue(checks["installed"].ok)
        self.assertIn("1.18.14", checks["installed"].detail)
        self.assertTrue(checks["login"].ok)
        self.assertTrue(checks["model"].ok)
        self.assertTrue(checks["model_release"].ok)
        self.assertIn("2026-09-10", checks["model_release"].detail)
        self.assertTrue(checks["config"].ok)
        joined = " ".join(c.detail for c in checks.values())
        self.assertNotIn("auth.json", joined)

    def test_doctor_missing_bin(self):
        with mock.patch.dict(os.environ, {BIN_ENV: "/nonexistent/opencode"}):
            checks = oc.OpencodeBackend().doctor({})
        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)

    def test_setup_mentions_login_and_extra_usage(self):
        text = "\n".join(oc.OpencodeBackend().setup({}))
        self.assertIn("opencode auth login", text)
        self.assertIn("Extra Usage", text)


if __name__ == "__main__":
    unittest.main()
