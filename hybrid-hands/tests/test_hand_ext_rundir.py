"""hand-ext runner: a hand deleting its run dir mid-run must not lose the outcome."""
from __future__ import annotations

import datetime as dt
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

PLUGIN_LIB = Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))

from hand_ext.backends.base import Backend, RunSpec, RunState, Status, Usage  # noqa: E402
from hand_ext.runner import run_backend  # noqa: E402
from hand_ext_case import HandExtTestCase  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fixtures" / "hand_ext" / "rundir_fake.py"
RUN_DIR_WARNING = "cảnh báo: thư mục lượt chạy bị xoá trong lúc chạy"
FINAL_TEXT = "BÁO CÁO GIẢ\n1. **Kết quả**: xong\n"
FAKE_STDERR = "fake backend: dọn file tạm trình duyệt"
EXPECTED_INPUT = 1234
EXPECTED_CACHED_INPUT = 56
EXPECTED_OUTPUT = 78
TIMEOUT_S = 30


class RundirBackend(Backend):
    """In-process backend whose child script deletes `spec.run_dir` before reporting."""

    name = "rundir"

    def __init__(self, delete: bool = True) -> None:
        self.delete = delete

    def setup(self, options: dict) -> list:
        return []

    def doctor(self, options: dict) -> list:
        return []

    def build_command(self, spec: RunSpec) -> tuple:
        mode = "delete" if self.delete else "keep"
        return [sys.executable, str(FAKE), str(spec.run_dir), mode], {}, None

    def parse_line(self, line: str, state: RunState) -> None:
        event = json.loads(line)
        if "final" in event:
            state.final_text = event["final"]
            return
        state.usage = Usage(input=int(event["input"]),
                            cached_input=int(event["cached_input"]),
                            output=int(event["output"]))

    def finalize(self, spec: RunSpec, state: RunState, exit_code: int,
                 stderr_text: str) -> Status:
        state.extra["stderr_text"] = stderr_text
        return Status.OK if exit_code == 0 else Status.FAILED


class RunDirDeletedTest(HandExtTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="hand-ext-rundir-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.run_dir = self.tmp / "output" / "llm" / "hand-ext" / "run-1"

    def _run(self, delete: bool = True) -> tuple:
        spec = RunSpec(prompt="MỤC TIÊU: thử\n", cwd=self.tmp, run_dir=self.run_dir,
                       model="", effort="", sandbox="read-only", timeout_s=TIMEOUT_S,
                       max_tokens=None, options={})
        err = io.StringIO()
        with redirect_stderr(err):
            outcome = run_backend(RundirBackend(delete=delete), spec)
        return outcome, err.getvalue()

    def test_deleted_run_dir_keeps_status_tokens_and_stderr(self) -> None:
        outcome, _ = self._run()
        self.assertEqual(outcome.status, Status.OK)
        self.assertEqual(outcome.state.usage.input, EXPECTED_INPUT)
        self.assertEqual(outcome.state.usage.cached_input, EXPECTED_CACHED_INPUT)
        self.assertEqual(outcome.state.usage.output, EXPECTED_OUTPUT)
        self.assertIn(FAKE_STDERR, outcome.state.extra["stderr_text"])
        self.assertEqual(outcome.state.final_text, FINAL_TEXT)

    def test_deleted_run_dir_is_recreated_with_report_and_one_warning(self) -> None:
        _, err = self._run()
        self.assertEqual(err.strip(), RUN_DIR_WARNING)
        self.assertTrue(self.run_dir.is_dir())
        report = self.run_dir / "report.md"
        self.assertEqual(report.read_text(encoding="utf-8"), FINAL_TEXT)

    def test_intact_run_dir_has_no_warning(self) -> None:
        outcome, err = self._run(delete=False)
        self.assertEqual(outcome.status, Status.OK)
        self.assertNotIn(RUN_DIR_WARNING, err)
        report = self.run_dir / "report.md"
        self.assertEqual(report.read_text(encoding="utf-8"), FINAL_TEXT)

    def test_events_get_ts_without_changing_fields(self) -> None:
        self._run(delete=False)
        lines = (self.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        expected = [{"input": EXPECTED_INPUT, "cached_input": EXPECTED_CACHED_INPUT,
                     "output": EXPECTED_OUTPUT}, {"final": FINAL_TEXT}]
        for line, original in zip(lines, expected):
            event = json.loads(line)
            self.assertIsNotNone(dt.datetime.fromisoformat(event.pop("ts")).tzinfo)
            self.assertEqual(event, original)


if __name__ == "__main__":
    unittest.main()
