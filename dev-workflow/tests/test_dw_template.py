"""Tests for scripts/dw_template.py and `dw template`."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import (
    SCRIPTS_DIR, SUBPROCESS_TIMEOUT_SECONDS, TEMPLATES_DIR, requires_tomllib, run_script, write_config,
    write_file,
)

EXIT_OK = 0
EXIT_ERROR = 2
REPO_TEMPLATES = "docs/templates"
CONFIG = f'[paths]\ntemplates = "{REPO_TEMPLATES}"\n'


@requires_tomllib
class DwTemplateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def resolve(self, name: str) -> tuple[str, str]:
        result = run_script("dw_template.py", [name], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        return result.stdout.strip(), result.stderr.strip()

    def test_design_uses_repo_spec_alias(self) -> None:
        write_config(self.root, CONFIG)
        spec = write_file(self.root, f"{REPO_TEMPLATES}/spec.md", "# spec\n")
        self.assertEqual(self.resolve("design"), (str(spec), "source: repo"))

    def test_repo_file_with_exact_name_wins_over_alias(self) -> None:
        write_config(self.root, CONFIG)
        write_file(self.root, f"{REPO_TEMPLATES}/spec.md", "# spec\n")
        design = write_file(self.root, f"{REPO_TEMPLATES}/design.md", "# design\n")
        self.assertEqual(self.resolve("design"), (str(design), "source: repo"))

    def test_missing_repo_template_falls_back_to_plugin(self) -> None:
        write_config(self.root, CONFIG)
        write_file(self.root, f"{REPO_TEMPLATES}/plan.md", "# plan\n")
        self.assertEqual(self.resolve("bug"), (str(TEMPLATES_DIR / "bug.md"), "source: plugin"))

    def test_custom_alias(self) -> None:
        write_config(self.root, CONFIG + 'template_aliases = { plan = "work-plan.md" }\n')
        plan = write_file(self.root, f"{REPO_TEMPLATES}/work-plan.md", "# plan\n")
        write_file(self.root, f"{REPO_TEMPLATES}/spec.md", "# spec\n")
        self.assertEqual(self.resolve("plan"), (str(plan), "source: repo"))
        # A custom table replaces the default, so spec.md no longer stands in for design.
        self.assertEqual(self.resolve("design"), (str(TEMPLATES_DIR / "design.md"), "source: plugin"))

    def test_empty_templates_setting_uses_plugin(self) -> None:
        write_config(self.root, "")
        write_file(self.root, "spec.md", "# spec\n")
        self.assertEqual(self.resolve("design"), (str(TEMPLATES_DIR / "design.md"), "source: plugin"))

    def test_no_config_uses_plugin(self) -> None:
        self.assertEqual(self.resolve("adr"), (str(TEMPLATES_DIR / "adr.md"), "source: plugin"))

    def test_unknown_name_exits_2(self) -> None:
        write_config(self.root, CONFIG)
        result = run_script("dw_template.py", ["brainstorm"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertIn("unknown template 'brainstorm'", result.stderr)

    def test_every_name_has_a_plugin_template(self) -> None:
        from dw_template import TEMPLATE_NAMES

        for name in TEMPLATE_NAMES:
            self.assertTrue((TEMPLATES_DIR / f"{name}.md").is_file(), name)

    def test_dw_template_subcommand_with_explicit_config(self) -> None:
        config = write_config(self.root, CONFIG)
        spec = write_file(self.root, f"{REPO_TEMPLATES}/spec.md", "# spec\n")
        result = subprocess.run(
            [str(SCRIPTS_DIR / "dw"), "template", "design", "--config", str(config)],
            cwd=SCRIPTS_DIR, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
        )
        if "no Python >= 3.11" in result.stderr:
            self.skipTest("no Python >= 3.11 or uv on PATH")
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout.strip(), str(spec))


if __name__ == "__main__":
    unittest.main()
