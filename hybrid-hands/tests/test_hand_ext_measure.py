"""hand-ext measure: đếm dòng test/code/docs và thời gian lệnh test theo lượt."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN_LIB = Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))

from hand_ext import cli, measure  # noqa: E402

PATCH = """\
diff --git a/tests/test_sample.py b/tests/test_sample.py
--- a/tests/test_sample.py
+++ b/tests/test_sample.py
@@ -1 +1,4 @@
 old
+def test_one():
+    assert True
+    assert True
diff --git a/lib/sample.py b/lib/sample.py
--- a/lib/sample.py
+++ b/lib/sample.py
@@ -1 +1,3 @@
 old
+x = 1
+y = 2
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
 old
+ghi chú
"""


class MeasureTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def _run(self, runs: Path, *, meta: bool = True, timestamps: bool = True) -> Path:
        run = runs / "20261106-100000-sample-dsh"
        run.mkdir(parents=True)
        (run / "changes.patch").write_text(PATCH, encoding="utf-8")
        events = [
            {"type": "tool_call", "callId": "c1", "tool": "bash",
             "input": {"command": "python3 -m pytest -q"}},
            {"type": "tool_result", "callId": "c1", "status": "completed"},
            {"type": "tool_call", "callId": "c2", "tool": "bash",
             "input": {"command": "ls"}},
            {"type": "tool_result", "callId": "c2", "status": "completed"},
        ]
        if timestamps:
            stamps = ("10:00:00", "10:00:05", "10:00:06", "10:00:07")
            for event, stamp in zip(events, stamps):
                event["ts"] = f"2026-11-06T{stamp}+00:00"
        (run / "events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
        if meta:
            (run / "meta.json").write_text(json.dumps({
                "plugin_version": "0.22.0", "backend": "dsh",
            }), encoding="utf-8")
        return run

    def test_cli_counts_lines_and_test_seconds(self) -> None:
        runs = self.base / "runs"
        self._run(runs)
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["measure", "--runs", str(runs)])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("| 20261106-100000-sample-dsh | 0.22.0 | dsh | 3 | 2 | 1 | "
                      "60.0% | 1 | 5.0 | 7.0 |", text)
        self.assertIn("| 0.22.0 | 1 | 3 | 2 | 1 | 60.0% | 3.0 | 3.0 |", text)

    def test_missing_meta_and_ts_still_counts_lines(self) -> None:
        runs = self.base / "runs"
        self._run(runs, meta=False, timestamps=False)
        rows = measure.collect_runs([runs])
        self.assertEqual(len(rows), 1)
        run = rows[0]
        self.assertEqual((run.test_lines, run.code_lines, run.docs_lines), (3, 2, 1))
        self.assertEqual(run.version, "unknown")
        self.assertIsNone(run.test_seconds)
        self.assertIn("unknown", measure.format_report(rows))
