"""Tests for trace_check rules: waivers, duplicate definitions, malformed IDs."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import requires_tomllib, run_script, write_config, write_file
from test_trace_check import CONFIG, PLAN, SRS, TEST_BOTH, TEST_ONLY_FIRST, TRACE_FILE

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_CONFIG_ERROR = 2
WAIVER_REASON = "Chỉ kiểm bằng UAT thủ công"
MALFORMED_SRS = """# Phụ lục

| ID | Mô tả |
|---|---|
| FR-Auth-1 | Sai hoa và thiếu chữ số |
| `FR_auth_001` | Dùng gạch dưới |
| **FR-001** | Thiếu feature |
| E-mail | Không phải ID, không cảnh báo |
"""


@requires_tomllib
class TraceRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        write_config(self.root, CONFIG)
        write_file(self.root, "docs/login/srs/spec.md", SRS)
        write_file(self.root, "docs/plans/login-plan.md", PLAN)
        write_file(self.root, "tests/test_login.py", TEST_BOTH)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def with_waivers(self, table: str) -> None:
        write_config(self.root, CONFIG + f"waivers = {table}\n")

    def run_json(self, expected_code: int) -> tuple[dict, subprocess.CompletedProcess[str]]:
        result = run_script("trace_check.py", ["--format", "json"], cwd=self.root)
        self.assertEqual(result.returncode, expected_code, result.stderr)
        return json.loads(result.stdout), result

    def test_waived_id_does_not_count_as_missing(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_ONLY_FIRST)
        self.with_waivers(f'{{ "FR-login-002" = "{WAIVER_REASON}" }}')
        report, _ = self.run_json(EXIT_OK)
        self.assertEqual(report["summary"]["missing_test"], [])
        self.assertEqual(report["summary"]["waived"], ["FR-login-002"])
        self.assertEqual(report["waivers"], {"FR-login-002": WAIVER_REASON})

    def test_waiver_section_in_markdown(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_ONLY_FIRST)
        self.with_waivers(f'{{ "FR-login-002" = "{WAIVER_REASON}" }}')
        result = run_script("trace_check.py", ["--write"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        content = (self.root / TRACE_FILE).read_text(encoding="utf-8")
        self.assertIn("- **Miễn trừ:** 1.", content)
        self.assertIn("## 3. Miễn trừ", content)
        self.assertIn(f"| `FR-login-002` | {WAIVER_REASON} |", content)

    def test_missing_links_are_reported_as_errors(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_ONLY_FIRST)
        write_file(self.root, "docs/plans/login-plan.md", "- [ ] T-login-01 x — covers: FR-login-001\n")
        write_file(self.root, "docs/plans/extra.md", "- [ ] T-login-09 y — covers: FR-login-404\n")
        report, result = self.run_json(EXIT_ERRORS)
        self.assertEqual(report["errors"], [
            "FR-login-002 has no task (require_task_types)",
            "FR-login-002 has no test (require_test_types)",
        ])
        self.assertIn("error: FR-login-002 has no test (require_test_types)", result.stderr)
        self.assertIn("error: FR-login-002 has no task (require_task_types)", result.stderr)
        self.assertIn("warning: orphan FR-login-404", result.stderr)
        self.assertNotIn("error: orphan", result.stderr)

    def test_waiver_for_unknown_id_warns(self) -> None:
        self.with_waivers('{ "FR-login-404" = "đã bỏ" }')
        report, result = self.run_json(EXIT_OK)
        self.assertEqual(report["unknown_waivers"], {"FR-login-404": "đã bỏ"})
        self.assertIn("waiver for unknown ID FR-login-404", result.stderr)

    def test_waivers_must_be_table_of_strings(self) -> None:
        self.with_waivers('["FR-login-002"]')
        result = run_script("trace_check.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("trace.waivers: expected table of strings", result.stderr)

    def test_duplicate_definition_is_an_error(self) -> None:
        write_file(self.root, "docs/login/srs/flows.md", "## FR-login-001 Luồng đăng nhập\n")
        report, result = self.run_json(EXIT_ERRORS)
        self.assertFalse(report["ok"])
        self.assertEqual(report["summary"]["duplicates"], ["FR-login-001"])
        self.assertEqual(
            report["duplicates"]["FR-login-001"], ["docs/login/srs/flows.md:1", "docs/login/srs/spec.md:5"],
        )
        self.assertIn("error: FR-login-001 defined more than once", result.stderr)

    def test_duplicate_listed_in_markdown_summary(self) -> None:
        write_file(self.root, "docs/login/srs/flows.md", "## FR-login-001 Luồng đăng nhập\n")
        result = run_script("trace_check.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_ERRORS)
        self.assertIn("- **ID định nghĩa trùng** (lỗi): 1.", result.stdout)
        self.assertIn("- `FR-login-001`: `docs/login/srs/flows.md:1`, `docs/login/srs/spec.md:5`", result.stdout)

    def test_malformed_ids_warn_with_location(self) -> None:
        write_file(self.root, "docs/login/srs/appendix.md", MALFORMED_SRS)
        report, result = self.run_json(EXIT_OK)
        self.assertEqual(report["summary"]["malformed"], 3)
        self.assertEqual(report["malformed"], [
            {"text": "FR-Auth-1", "location": "docs/login/srs/appendix.md:5"},
            {"text": "FR_auth_001", "location": "docs/login/srs/appendix.md:6"},
            {"text": "FR-001", "location": "docs/login/srs/appendix.md:7"},
        ])
        self.assertIn("malformed ID 'FR-Auth-1' at docs/login/srs/appendix.md:5", result.stderr)

    def test_malformed_count_in_markdown_summary(self) -> None:
        write_file(self.root, "docs/login/srs/appendix.md", MALFORMED_SRS)
        result = run_script("trace_check.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn("- **ID sai định dạng** (cảnh báo): 3.", result.stdout)
        self.assertIn("- `FR-Auth-1`: `docs/login/srs/appendix.md:5`", result.stdout)


class MalformedCellTest(unittest.TestCase):
    def setUp(self) -> None:
        from trace_scan import IdMatcher

        self.matcher = IdMatcher(["FR", "NFR", "BR", "E", "SC"])

    def test_valid_and_non_id_cells_are_not_malformed(self) -> None:
        for cell in (" FR-auth-001 ", "`SC-auth-01`", "ID", "E-mail", "Mô tả FR-1 trong câu"):
            self.assertFalse(self.matcher.is_malformed_cell(cell), cell)

    def test_bad_cells_are_malformed(self) -> None:
        for cell in ("FR-Auth-1", "FR_auth_001", "FR-001", "NFR-auth-0001"):
            self.assertTrue(self.matcher.is_malformed_cell(cell), cell)


if __name__ == "__main__":
    unittest.main()
