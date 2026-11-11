"""Tests for plan_status.py (status page from Markdown plans)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, requires_tomllib, run_script, write_file

DONE_PLAN = "---\nstatus: completed\n---\n# M0 Nền tảng\n\n- [x] a\n- [x] b\n"
OPEN_PLAN = "# M1 Trò chơi\n\n- [x] c\n- [ ] d\n- [ ] e\n- [-] ~~f~~ — bỏ\n"


@requires_tomllib
class PlanStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        write_file(self.repo, "docs/plans/m0.md", DONE_PLAN)
        write_file(self.repo, "docs/plans/m1.md", OPEN_PLAN)
        write_file(self.repo, "docs/work-in-progress/handoffs/x.md", "# Bàn giao Z\n\n- [ ] handoff-task\n")
        self.md = self.repo / "docs/status/plan-status.md"

    def run_tool(self, *extra: str) -> None:
        result = run_script("plan_status.py", ["--repo", str(self.repo), *extra], self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_summary_table_and_pie(self) -> None:
        self.run_tool()
        text = self.md.read_text(encoding="utf-8")
        self.assertIn("60% (3/5 task xong, 1 bỏ)", text)
        self.assertIn("[M0 Nền tảng](../plans/m0.md)", text)
        self.assertNotIn("handoff-task", text)
        self.assertNotIn(str(self.repo), text)
        self.assertIn("▓▓▓░░░░░░░ 33%", text)
        self.assertIn("pie showData", text)
        self.assertIn("flowchart LR", text)

    def test_rerun_keeps_manual_block(self) -> None:
        self.run_tool()
        text = self.md.read_text(encoding="utf-8").replace("_Ghi chú, rủi ro", "Rủi ro X\n_Ghi chú, rủi ro")
        self.md.write_text(text, encoding="utf-8")
        self.run_tool()
        self.assertIn("Rủi ro X", self.md.read_text(encoding="utf-8"))

    def test_html_is_self_contained(self) -> None:
        self.run_tool("--html")
        page = (self.repo / "docs/status/plan-status.html").read_text(encoding="utf-8")
        self.assertNotIn("<script", page)
        self.assertNotIn("http", page)
        self.assertIn("<svg", page)
        self.assertNotIn("— _", page)

    def test_pages_index_and_single_page(self) -> None:
        write_file(self.repo, ".claude/plan-status.toml", PAGES_TOML)
        self.run_tool("--page", "b")
        self.assertFalse((self.repo / "docs/status/a.md").exists())
        self.assertFalse((self.repo / "docs/status/README.md").exists())
        result = subprocess.run([str(SCRIPTS_DIR / "dw"), "plan-status", "--repo", str(self.repo)],
                                capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        a, b = (self.repo / f"docs/status/{n}.md" for n in "ab")
        self.assertIn("M0 Nền tảng", a.read_text(encoding="utf-8"))
        self.assertNotIn("M1 Trò chơi", a.read_text(encoding="utf-8"))
        self.assertIn("# Trang B", b.read_text(encoding="utf-8"))
        index = (self.repo / "docs/status/README.md").read_text(encoding="utf-8")
        self.assertIn("[Trang A](a.md)", index)
        self.assertIn("[Trang B](b.md)", index)


PAGES_TOML = """[[page]]
name = "a"
title = "Trang A"
include = ["docs/plans/*.md"]
exclude_files = ["docs/plans/m1.md"]
out = "docs/status/a.md"
[[page]]
name = "b"
title = "Trang B"
include = ["docs/plans/m1.md"]
out = "docs/status/b.md"
"""


if __name__ == "__main__":
    unittest.main()
