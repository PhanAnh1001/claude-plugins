"""hand-ext dsh backend: argv/env, `.env` isolation, NDJSON usage, classification, doctor."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from hand_ext.backends.base import RunSpec, RunState, Status, Usage  # noqa: E402
from hand_ext.backends import dsh  # noqa: E402
from hand_ext.runner import run_backend  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "hand_ext"
FAKE_BIN = FIXTURES / "dsh_fake.py"
BIN_ENV = "HAND_EXT_DSH_BIN"
TIMEOUT_S = 60
FAKE_KEY = "test-go-key-not-real"
REPO_SECRET = "REPO_SECRET_VALUE_SHOULD_NOT_LEAK"
FOREIGN_KEYS = {"GEMINI_API_KEY": "g", "DEEPSEEK_API_KEY": "d", "OPENAI_API_KEY": "o",
                "ANTHROPIC_API_KEY": "a", "OPENCODE_API_KEY": "c"}


class _Home:
    """Temporary DSH_HOME prepared like `hand-ext setup`, plus a key file at mode 600."""

    def __init__(self, base: Path, key: bool = True):
        self.options = {"home": str(base / "home"), "key_file": str(base / "home" / "go.key")}
        dsh.DshBackend().setup(self.options)
        if key:
            path = dsh.key_file(self.options)
            path.write_text(FAKE_KEY + "\n", encoding="utf-8")
            path.chmod(dsh.KEY_FILE_MODE)


def _spec(base: Path, options: dict, cwd: Path, effort: str = "max",
          model: str = dsh.DEFAULT_MODEL, sandbox: str = "workspace-write") -> RunSpec:
    return RunSpec(prompt="PREAMBLE\n\n## BRIEF\n\nbrief body", cwd=cwd,
                   run_dir=base / "runs" / "20261104-run-dsh", model=model, effort=effort,
                   sandbox=sandbox, timeout_s=TIMEOUT_S, max_tokens=None, options=options)


def _feed(name: str) -> RunState:
    state = RunState(usage=Usage())
    backend = dsh.DshBackend()
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        backend.parse_line(line, state)
    return state


class _TmpCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / ".env").write_text("GEMINI_API_KEY=%s\n" % REPO_SECRET, encoding="utf-8")


class BuildCommandTest(_TmpCase):
    def setUp(self):
        super().setUp()
        self.home = _Home(self.base)
        patcher = mock.patch.dict(os.environ, {BIN_ENV: "/fake/dsh"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_argv_env_and_stdin(self):
        spec = _spec(self.base, self.home.options, self.repo)
        argv, env, stdin = dsh.DshBackend().build_command(spec)
        launch = dsh.launch_dir(self.home.options)
        self.assertEqual(argv[:4], [sys.executable, "-c", dsh.CHDIR_EXEC, str(launch)])
        self.assertEqual(argv[4:], ["/fake/dsh", "--profile", "headless", "--patch",
                                    str(dsh.patch_file(self.home.options)), "--json", "-"])
        self.assertEqual(stdin, spec.prompt)
        self.assertEqual(env[dsh.KEY_ENV], FAKE_KEY)
        self.assertEqual(env[dsh.ENV_WORKSPACE], str(self.repo))
        value = env[dsh.ENV_SESSION]
        self.assertEqual(value, dsh.session_uuid(spec.run_dir.name))
        parsed = __import__("uuid").UUID(value)
        self.assertEqual(parsed.version, 5)
        self.assertEqual(str(parsed), value)
        self.assertNotIn(spec.run_dir.name, value)
        self.assertEqual(dsh.session_uuid(spec.run_dir.name), value)
        self.assertEqual(env[dsh.ENV_MODEL], dsh.DEFAULT_MODEL)
        self.assertEqual(env[dsh.ENV_EFFORT], "max")
        self.assertEqual(env[dsh.ENV_BASE_URL], dsh.DEFAULT_BASE_URL)
        self.assertEqual(env[dsh.ENV_PERMISSION], "workspace-write")
        self.assertEqual(env[dsh.ENV_TELEMETRY], dsh.TELEMETRY_OFF)

    def test_effort_and_model_prefix(self):
        spec = _spec(self.base, self.home.options, self.repo, effort="medium",
                     model="opencode-go/deepseek-v4.1-flash")
        _, env, _ = dsh.DshBackend().build_command(spec)
        self.assertEqual(env[dsh.ENV_EFFORT], dsh.DEFAULT_EFFORT)
        self.assertEqual(env[dsh.ENV_MODEL], "deepseek-v4.1-flash")
        with self.assertRaises(ValueError):
            dsh.DshBackend().build_command(
                _spec(self.base, self.home.options, self.repo, model="deepseek/x"))

    def test_missing_key_refuses(self):
        dsh.key_file(self.home.options).unlink()
        with self.assertRaises(ValueError):
            dsh.DshBackend().build_command(_spec(self.base, self.home.options, self.repo))

    def test_key_file_must_be_600(self):
        dsh.key_file(self.home.options).chmod(0o644)
        with self.assertRaises(ValueError):
            dsh.DshBackend().build_command(_spec(self.base, self.home.options, self.repo))

    def test_home_env_refuses(self):
        (dsh.home_dir(self.home.options) / ".env").write_text("X=1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            dsh.DshBackend().build_command(_spec(self.base, self.home.options, self.repo))

    def test_blocked_env_covers_paid_keys(self):
        for key in FOREIGN_KEYS:
            self.assertIn(key, dsh.DshBackend.BLOCKED_ENV)
        self.assertIn(dsh.KEY_ENV, dsh.DshBackend.BLOCKED_ENV)

    def test_template_routes_go(self):
        text = dsh.TEMPLATE_PATCH.read_text(encoding="utf-8")
        for needle in ("apiKeyEnv: %s" % dsh.KEY_ENV, "api: openai-completions",
                       "x-opencode-session: !!js process.env.%s" % dsh.ENV_SESSION,
                       "cwd: !!js process.env.%s" % dsh.ENV_WORKSPACE, "policy: never",
                       "thinkingFormat: deepseek"):
            self.assertIn(needle, text)


class RunIsolationTest(_TmpCase):
    """End to end through runner.run_backend with the fake dsh."""

    def _run(self, scenario: str):
        home = _Home(self.base)
        probe = self.base / "probe.json"
        env = dict(FOREIGN_KEYS, **{BIN_ENV: str(FAKE_BIN), "FAKE_DSH_PROBE": str(probe),
                                    "FAKE_DSH_SCENARIO": scenario,
                                    "FAKE_DSH_EXPECT_KEY": FAKE_KEY})
        spec = _spec(self.base, home.options, self.repo)
        with mock.patch.dict(os.environ, env):
            outcome = run_backend(dsh.DshBackend(), spec)
        return outcome, json.loads(probe.read_text(encoding="utf-8")), home, spec

    def test_success_isolated_from_repo_env(self):
        outcome, seen, home, spec = self._run("success")
        self.assertEqual(outcome.status, Status.OK)
        self.assertEqual(Path(seen["cwd"]).resolve(), dsh.launch_dir(home.options).resolve())
        self.assertFalse(seen["dotenv_loaded"])
        self.assertEqual(seen["api_key_names"], [dsh.KEY_ENV])
        self.assertTrue(seen["go_key_matches"])
        self.assertEqual(seen["hand_env"][dsh.ENV_WORKSPACE], str(self.repo))
        self.assertEqual(seen["dsh_env"]["DSH_TELEMETRY_MODE"], dsh.TELEMETRY_OFF)
        self.assertEqual(seen["stdin"], spec.prompt)
        report = (spec.run_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("Kết quả", report)
        for path in spec.run_dir.iterdir():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(FAKE_KEY, text)
            self.assertNotIn(REPO_SECRET, text)

    def test_quota(self):
        outcome, _, _, _ = self._run("quota")
        self.assertEqual(outcome.status, Status.QUOTA)

    def test_missing_credential(self):
        outcome, _, _, _ = self._run("nokey")
        self.assertEqual(outcome.status, Status.NOT_LOGGED_IN)

    def test_wrapper_never_opens_repo_env(self):
        real_open = open
        opened = []

        def spy(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", spy):
            self._run("success")
        self.assertNotIn(str(self.repo / ".env"), opened)


class ParseAndFinalizeTest(unittest.TestCase):
    def setUp(self):
        self.spec = RunSpec(prompt="", cwd=Path("/repo"), run_dir=Path("/tmp/x"), model="",
                            effort="", sandbox="", timeout_s=1, max_tokens=None, options={})
        self.backend = dsh.DshBackend()

    def test_success_usage_summed(self):
        state = _feed("dsh_success.jsonl")
        self.assertEqual(state.usage.input, 1200 + 4000 + 800 + 5000 + 20)
        self.assertEqual(state.usage.cached_input, 9000)
        self.assertEqual(state.usage.output, 450)
        self.assertTrue(state.final_text.startswith("**Kết quả**"))
        self.assertEqual(self.backend.finalize(self.spec, state, 0, ""), Status.OK)

    def test_quota_and_auth_codes(self):
        self.assertEqual(self.backend.finalize(self.spec, _feed("dsh_quota.jsonl"), 1, ""),
                         Status.QUOTA)
        self.assertEqual(self.backend.finalize(self.spec, _feed("dsh_nokey.jsonl"), 1, ""),
                         Status.NOT_LOGGED_IN)

    def test_stderr_only_and_plain_failure(self):
        empty = RunState(usage=Usage())
        self.assertEqual(self.backend.finalize(self.spec, empty, 1, "dsh: AUTH: 401"),
                         Status.NOT_LOGGED_IN)
        self.backend.parse_line("not json", empty)
        self.backend.parse_line("{broken", empty)
        self.assertEqual(self.backend.finalize(self.spec, empty, 1, "boom"), Status.FAILED)
        self.assertEqual(self.backend.finalize(self.spec, RunState(usage=Usage()), 0, ""),
                         Status.FAILED)


class DoctorTest(_TmpCase):
    def test_doctor_ready_with_fake_bin(self):
        home = _Home(self.base)
        with mock.patch.dict(os.environ, {BIN_ENV: str(FAKE_BIN)}):
            checks = {c.name: c for c in dsh.DshBackend().doctor(home.options)}
        self.assertTrue(all(c.ok for c in checks.values()), checks)
        self.assertIn("0.2.1-rc.5", checks["installed"].detail)
        self.assertNotIn(FAKE_KEY, " ".join(c.detail for c in checks.values()))

    def test_doctor_without_key(self):
        home = _Home(self.base, key=False)
        with mock.patch.dict(os.environ, {BIN_ENV: str(FAKE_BIN)}):
            checks = {c.name: c for c in dsh.DshBackend().doctor(home.options)}
        self.assertFalse(checks["key_file"].ok)

    def test_doctor_flags_home_env(self):
        home = _Home(self.base)
        (dsh.home_dir(home.options) / ".env").write_text("X=1\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {BIN_ENV: str(FAKE_BIN)}):
            checks = {c.name: c for c in dsh.DshBackend().doctor(home.options)}
        self.assertFalse(checks["home_env"].ok)

    def test_doctor_missing_bin(self):
        with mock.patch.dict(os.environ, {BIN_ENV: "/nonexistent/dsh"}):
            checks = dsh.DshBackend().doctor({"home": str(self.base / "h")})
        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)

    def test_setup_lines(self):
        options = {"home": str(self.base / "h"), "key_file": str(self.base / "h" / "go.key")}
        text = "\n".join(dsh.DshBackend().setup(options))
        self.assertIn("chmod 600", text)
        self.assertIn("Extra Usage", text)
        self.assertTrue(dsh.patch_file(options).is_file())
        self.assertFalse(dsh.key_file(options).exists())
        self.assertTrue(dsh.launch_dir(options).is_dir())


if __name__ == "__main__":
    unittest.main()
