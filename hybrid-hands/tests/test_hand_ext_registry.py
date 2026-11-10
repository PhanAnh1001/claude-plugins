"""Machine-wide registry of running `hand-ext run` attempts."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
PLUGIN_LIB = TESTS.parents[0] / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))
sys.path.insert(0, str(TESTS / "fixtures" / "hand_ext"))

from codex_harness import Sandbox  # noqa: E402
from hand_ext.backends.base import Usage  # noqa: E402
from hand_ext.run_registry import RunRegistry  # noqa: E402
from hand_ext_case import HandExtTestCase  # noqa: E402

STATE_ENV = "HYBRID_HANDS_STATE_DIR"
PARENT_ENV = "CLAUDE_CODE_SESSION_ID"
CLAUDE_PID_ENV = "CLAUDE_PID"
NOW = 1_700_000_000.0
INTERVAL = 15


class Clock:
    def __init__(self, value: float = NOW) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class RegistryFileTest(HandExtTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="hand-ext-registry-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.runs = self.tmp / "runs"
        self.clock = Clock()
        patcher = mock.patch.dict(os.environ, {PARENT_ENV: "sess-main",
                                               CLAUDE_PID_ENV: "4242"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def registry(self, run_id: str = "run-1") -> RunRegistry:
        return RunRegistry(
            runs_dir=self.runs, run_id=run_id, label="lab", backend="dsh",
            model="deepseek-v4.1-flash", cwd=Path("fake-project"),
            run_dir=Path("fake-output") / run_id, clock=self.clock)

    def path(self, run_id: str = "run-1") -> Path:
        return self.runs / f"{run_id}.json"

    def read(self, run_id: str = "run-1") -> dict:
        return json.loads(self.path(run_id).read_text(encoding="utf-8"))

    def test_start_records_parent_env_and_running_state(self) -> None:
        with mock.patch.dict(os.environ, {"HYBRID_HANDS_HAND_SCOPE": "fake-cap-key"}):
            self.registry().start()
        data = self.read()
        self.assertEqual(data["run_id"], "run-1")
        self.assertEqual(data["label"], "lab")
        self.assertEqual(data["backend"], "dsh")
        self.assertEqual(data["model"], "deepseek-v4.1-flash")
        self.assertEqual(data["cwd"], "fake-project")
        self.assertEqual(data["run_dir"], str(Path("fake-output") / "run-1"))
        self.assertEqual(data["pid"], os.getpid())
        self.assertEqual(data["parent_session"], "sess-main")
        self.assertEqual(data["parent_claude_pid"], 4242)
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["tokens"], {"input": 0, "cached_input": 0, "output": 0})
        self.assertEqual(data["updated_at"], int(NOW))
        self.assertTrue(data["started"])

    def test_tick_updates_tokens_at_most_once_per_15_seconds(self) -> None:
        registry = self.registry()
        registry.start()
        registry.tick(Usage(input=100, cached_input=10, output=20))
        self.assertEqual(self.read()["tokens"], {"input": 0, "cached_input": 0, "output": 0})
        self.clock.value += INTERVAL
        registry.tick(Usage(input=100, cached_input=10, output=20))
        self.assertEqual(self.read()["tokens"],
                         {"input": 100, "cached_input": 10, "output": 20})
        self.clock.value += 1
        registry.tick(Usage(input=999, cached_input=999, output=999))
        self.assertEqual(self.read()["tokens"],
                         {"input": 100, "cached_input": 10, "output": 20})

    def test_child_pid_is_recorded_once_available(self) -> None:
        registry = self.registry()
        registry.start()
        registry.child(31337)
        self.assertEqual(self.read()["child_pid"], 31337)

    def test_finish_writes_status_ended_tokens_and_exit(self) -> None:
        registry = self.registry()
        registry.start()
        self.clock.value += 42
        registry.finish("ok", 0, Usage(input=1000, cached_input=400, output=100))
        data = self.read()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["exit"], 0)
        self.assertEqual(data["tokens"],
                         {"input": 1000, "cached_input": 400, "output": 100})
        self.assertTrue(data["ended"])
        self.assertEqual(data["updated_at"], int(NOW + 42))

    def test_write_error_only_warns_and_never_raises(self) -> None:
        blocker = self.tmp / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        registry = RunRegistry(
            runs_dir=blocker / "runs", run_id="run-1", label="lab", backend="dsh",
            model="m", cwd=self.tmp, run_dir=self.tmp / "run", clock=self.clock)
        err = io.StringIO()
        with redirect_stderr(err):
            registry.start()
            self.clock.value += INTERVAL
            registry.tick(Usage(input=1, cached_input=2, output=3))
            registry.finish("failed", 1, Usage(input=1, cached_input=2, output=3))
        self.assertIn("cảnh báo", err.getvalue())
        self.assertFalse(self.path().exists())

    def test_read_only_runs_dir_only_warns(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can write into a read-only directory")
        self.runs.mkdir()
        self.runs.chmod(0o500)
        self.addCleanup(self.runs.chmod, 0o700)
        registry = self.registry()
        err = io.StringIO()
        with redirect_stderr(err):
            registry.start()
            self.clock.value += INTERVAL
            registry.tick(Usage(input=1, cached_input=2, output=3))
            registry.finish("failed", 1, Usage(input=1, cached_input=2, output=3))
        self.assertIn("cảnh báo", err.getvalue())
        self.assertFalse(self.path().exists())

    def test_cleanup_removes_only_finished_files_older_than_seven_days(self) -> None:
        self.runs.mkdir()
        old_finished = {"run_id": "old", "status": "ok",
                        "ended": "2023-11-05T00:00:00+00:00", "tokens": {}}
        old_running = {"run_id": "old-run", "status": "running", "pid": os.getpid()}
        self.path("old").write_text(json.dumps(old_finished), encoding="utf-8")
        self.path("old-run").write_text(json.dumps(old_running), encoding="utf-8")
        self.registry("new").start()
        self.assertFalse(self.path("old").exists())
        self.assertTrue(self.path("old-run").exists())
        self.assertTrue(self.path("new").exists())


class RegistryRunIntegrationTest(HandExtTestCase):
    def setUp(self) -> None:
        self.sb = Sandbox(order=["codex"])
        self.addCleanup(self.sb.close)
        self.state = self.sb.dir / "machine-state"
        patcher = mock.patch.dict(os.environ, {
            STATE_ENV: str(self.state), PARENT_ENV: "sess-from-env",
            CLAUDE_PID_ENV: "9876"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def entries(self) -> list:
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((self.state / "runs").glob("*.json"))]

    def test_real_run_writes_final_entry_with_parent_and_child_pid(self) -> None:
        self.sb.scenario("ok")
        code, out, err = self.sb.cli("run", "--brief", str(self.sb.brief),
                                     "--backend", "codex")
        self.assertEqual(code, 0, (out, err))
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["exit"], 0)
        self.assertEqual(entry["parent_session"], "sess-from-env")
        self.assertEqual(entry["parent_claude_pid"], 9876)
        self.assertIsInstance(entry["child_pid"], int)
        self.assertGreater(entry["tokens"]["input"], 0)
        self.assertTrue(entry["ended"])

    def test_unwritable_registry_does_not_fail_the_run(self) -> None:
        blocker = self.sb.dir / "state-file"
        blocker.write_text("not a directory", encoding="utf-8")
        with mock.patch.dict(os.environ, {STATE_ENV: str(blocker)}):
            self.sb.scenario("ok")
            code, out, err = self.sb.cli("run", "--brief", str(self.sb.brief),
                                         "--backend", "codex")
        self.assertEqual(code, 0, (out, err))
        self.assertIn("cảnh báo", err)
        self.assertEqual(len(self.sb.ledger()), 1)


if __name__ == "__main__":
    unittest.main()


def setUpModule():  # keep hh-store revision bumps out of the real ~/.hybrid-hands
    import os as _os, tempfile as _tempfile
    from unittest import mock as _mock
    global _STATE_TMP, _STATE_ENV
    _STATE_TMP = _tempfile.TemporaryDirectory()
    _STATE_ENV = _mock.patch.dict(_os.environ, {"HYBRID_HANDS_STATE_DIR": _STATE_TMP.name})
    _STATE_ENV.start()


def tearDownModule():
    _STATE_ENV.stop()
    _STATE_TMP.cleanup()
