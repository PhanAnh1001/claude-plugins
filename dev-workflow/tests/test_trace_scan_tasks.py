"""Tests for plan task parsing in scripts/trace_scan.py: skipped tasks are not tasks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import write_file

ID_TYPES = ["FR", "NFR", "BR", "E", "SC"]
PLAN_FILE = "docs/plans/plan.md"

PLAN_WITH_SKIPPED = """# Kế hoạch

- [x] T-x-03 Làm xong — covers: FR-x-003
- [ ] T-x-04 Chưa làm — covers: FR-x-004, E-x-001
- [-] ~~T-x-01 Bỏ việc này~~ — bỏ qua: không cần nữa — covers: FR-x-001
- [x] ~~T-x-02 Bỏ việc kia~~ — bỏ qua: đổi hướng — covers: FR-x-002
"""


class SkippedTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        from trace_scan import IdMatcher, ScanResult, scan_plans

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        write_file(root, PLAN_FILE, PLAN_WITH_SKIPPED)
        self.result = ScanResult()
        scan_plans(root, [PLAN_FILE], IdMatcher(ID_TYPES), self.result)
        self.tasks = {task.task_id: task for task in self.result.tasks}
        self.covered = {covered for task in self.result.tasks for covered in task.covers}

    def test_dash_checkbox_line_is_not_a_task(self) -> None:
        self.assertNotIn("T-x-01", self.tasks)
        self.assertNotIn("FR-x-001", self.covered)

    def test_struck_through_ticked_line_is_not_a_task(self) -> None:
        self.assertNotIn("T-x-02", self.tasks)
        self.assertNotIn("FR-x-002", self.covered)

    def test_open_and_done_lines_parse_as_before(self) -> None:
        self.assertEqual(set(self.tasks), {"T-x-03", "T-x-04"})
        self.assertTrue(self.tasks["T-x-03"].done)
        self.assertEqual(self.tasks["T-x-03"].covers, ["FR-x-003"])
        self.assertFalse(self.tasks["T-x-04"].done)
        self.assertEqual(self.tasks["T-x-04"].covers, ["FR-x-004", "E-x-001"])


if __name__ == "__main__":
    unittest.main()
