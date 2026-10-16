"""Tests for scripts/trace_check.py and scripts/trace_scan.py (fixtures built in a tempdir)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import requires_tomllib, run_script, write_config, write_file

EXIT_OK = 0
EXIT_MISSING_LINKS = 1
EXIT_CONFIG_ERROR = 2
TRACE_FILE = "docs/_shared/traceability.md"

CONFIG = """
[paths]
srs = ["docs/**/srs/*.md"]
plans = "docs/plans"
traceability = "docs/_shared/traceability.md"

[trace]
test_globs = ["tests/**/*.py"]
"""

SRS = """# Đặc tả đăng nhập

| ID | Mô tả | Verify by |
|---|---|---|
| FR-login-001 | Đăng nhập bằng mật khẩu | unit |
| `FR-login-002` | Khoá tài khoản sau 5 lần sai, xem FR-login-001 | unit |
| E-login-001 | Sai mật khẩu | unit |

### NFR-login-001 Thời gian phản hồi

Đăng nhập dưới 1 giây.
"""

PLAN = """# Kế hoạch

- [x] T-login-01 Form đăng nhập — covers: FR-login-001, E-login-001
- [ ] T-login-02 Khoá tài khoản — covers: FR-login-002
"""

TEST_BOTH = """# FR-login-002 covered by a comment
def test_FR_login_001_password_ok():
    pass


def test_lockout():
    pass
"""

TEST_ONLY_FIRST = """def test_FR_login_001_password_ok():
    pass
"""


@requires_tomllib
class TraceCheckCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        write_config(self.root, CONFIG)
        write_file(self.root, "docs/login/srs/spec.md", SRS)
        write_file(self.root, "docs/plans/login-plan.md", PLAN)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_json(self) -> tuple[int, dict]:
        result = run_script("trace_check.py", ["--format", "json"], cwd=self.root)
        self.assertIn(result.returncode, (EXIT_OK, EXIT_MISSING_LINKS), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_all_links_present_exits_0(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_BOTH)
        code, report = self.run_json()
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["ids"], 4)
        self.assertEqual(report["summary"]["by_type"], {"E": 1, "FR": 2, "NFR": 1})
        rows = {row["id"]: row for row in report["rows"]}
        self.assertEqual(rows["FR-login-001"]["tasks"], [{"id": "T-login-01", "done": True}])
        self.assertEqual(rows["FR-login-001"]["tests"], ["tests/test_login.py"])
        self.assertEqual(rows["FR-login-002"]["tests"], ["tests/test_login.py"])
        self.assertEqual(rows["FR-login-001"]["defined_at"], ["docs/login/srs/spec.md:5"])
        self.assertEqual(report["summary"]["orphans"], [])

    def test_fr_without_test_exits_1(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_ONLY_FIRST)
        code, report = self.run_json()
        self.assertEqual(code, EXIT_MISSING_LINKS)
        self.assertEqual(report["summary"]["missing_test"], ["FR-login-002"])
        self.assertEqual(report["summary"]["missing_task"], [])

    def test_fr_without_task_exits_1(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_BOTH)
        write_file(self.root, "docs/plans/login-plan.md", "- [ ] T-login-01 x — covers: FR-login-001\n")
        code, report = self.run_json()
        self.assertEqual(code, EXIT_MISSING_LINKS)
        self.assertEqual(report["summary"]["missing_task"], ["FR-login-002"])

    def test_orphan_reference_is_warned(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_BOTH + "\n# FR-login-009 removed\n")
        write_file(self.root, "docs/plans/extra.md", "- [ ] T-login-03 y — covers: FR-login-001, BR-login-007\n")
        result = run_script("trace_check.py", ["--format", "json"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["summary"]["orphans"], ["BR-login-007", "FR-login-009"])
        self.assertIn("orphan FR-login-009", result.stderr)

    def test_write_creates_traceability_with_summary(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_ONLY_FIRST)
        result = run_script("trace_check.py", ["--write"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_MISSING_LINKS)
        content = (self.root / TRACE_FILE).read_text(encoding="utf-8")
        body = content.split("---", 2)[2]
        first_section = next(line for line in body.splitlines() if line.startswith("## "))
        self.assertEqual(first_section, "## Tóm tắt")
        self.assertIn("**Số ID:** 4", content)
        self.assertIn("**Thiếu test:** 1", content)
        self.assertIn("| `FR-login-001` | `docs/login/srs/spec.md:5` | `T-login-01` (xong) |", content)
        self.assertEqual(result.stdout, content)

    def test_rerun_after_write_ignores_generated_file(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_BOTH)
        # Put the generated file inside the SRS glob: its table rows must not count as definitions.
        config = CONFIG.replace("docs/_shared/traceability.md", "docs/login/srs/trace.md")
        write_config(self.root, config)
        first = run_script("trace_check.py", ["--write", "--format", "json"], cwd=self.root)
        second = run_script("trace_check.py", ["--format", "json"], cwd=self.root)
        self.assertEqual(first.returncode, EXIT_OK, first.stderr)
        self.assertEqual(second.returncode, EXIT_OK, second.stderr)
        self.assertNotIn("defined more than once", second.stderr)

    def test_explicit_config_flag(self) -> None:
        write_file(self.root, "tests/test_login.py", TEST_BOTH)
        elsewhere = self.root / "docs"
        result = run_script(
            "trace_check.py", ["--config", str(self.root / ".claude" / "dev-workflow.toml")], cwd=elsewhere,
        )
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)

    def test_missing_config_exits_2(self) -> None:
        (self.root / ".claude" / "dev-workflow.toml").unlink()
        result = run_script("trace_check.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)


class IdMatcherTest(unittest.TestCase):
    def setUp(self) -> None:
        from trace_scan import IdMatcher

        self.matcher = IdMatcher(["FR", "NFR", "BR", "E", "SC"])

    def test_underscore_form_maps_to_hyphen_id(self) -> None:
        self.assertEqual(self.matcher.all_ids("def test_NFR_login_flow_001_fast():"), ["NFR-login-flow-001"])

    def test_nfr_is_not_read_as_fr(self) -> None:
        self.assertEqual(self.matcher.hyphen_ids("see NFR-auth-001"), ["NFR-auth-001"])

    def test_number_must_be_2_or_3_digits(self) -> None:
        self.assertEqual(self.matcher.hyphen_ids("FR-x-1 FR-x-0001 SC-x-01 FR-x-001."), ["SC-x-01", "FR-x-001"])

    def test_glob_double_star_spans_directories(self) -> None:
        from trace_scan import glob_to_regex

        regex = glob_to_regex("docs/**/srs/*.md")
        self.assertTrue(regex.match("docs/srs/a.md"))
        self.assertTrue(regex.match("docs/a/b/srs/spec.md"))
        self.assertFalse(regex.match("docs/a/srs/sub/spec.md"))


if __name__ == "__main__":
    unittest.main()
