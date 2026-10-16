"""Tests for scripts/dw_config.py."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import TEMPLATES_DIR, requires_tomllib, run_script, write_config

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


@requires_tomllib
class DwConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve() / "my-repo"
        self.root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_empty_config_gets_all_defaults(self) -> None:
        import dw_config

        path = write_config(self.root, "")
        config = dw_config.load_config(path)
        self.assertEqual(config.root, self.root)
        self.assertEqual(config.data["project"]["name"], "my-repo")
        self.assertEqual(config.data["project"]["max_file_lines"], 400)
        self.assertEqual(config.data["trace"]["require_test_types"], ["FR"])
        self.assertEqual(config.data["jira"]["estimate_factor"], 1.1)
        self.assertEqual(config.data["lanes"]["l0_max_files"], 2)
        self.assertEqual(config.warnings, [])

    def test_migrations_and_frontend_defaults(self) -> None:
        import dw_config

        config = dw_config.load_config(write_config(self.root, ""))
        self.assertEqual(config.get("paths.migrations"), "")
        self.assertEqual(config.get("frontend"), {"dev_command": "", "checks": [], "ui_language": ""})

    def test_frontend_values_are_type_checked(self) -> None:
        write_config(self.root, '[frontend]\nchecks = "npm test"\n')
        result = run_script("dw_config.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("frontend.checks: expected list of strings", result.stderr)

    def test_frontend_values_override_defaults(self) -> None:
        import dw_config

        path = write_config(
            self.root, '[paths]\nmigrations = "db/migrations"\n[frontend]\ndev_command = "npm run dev"\n'
            'checks = ["npm test", "npm run build"]\nui_language = "en"\n',
        )
        config = dw_config.load_config(path)
        self.assertEqual(config.get("paths.migrations"), "db/migrations")
        self.assertEqual(config.get("frontend.checks"), ["npm test", "npm run build"])
        self.assertEqual(config.get("frontend.ui_language"), "en")

    def test_user_values_override_defaults(self) -> None:
        import dw_config

        path = write_config(self.root, '[gate]\ncommands = ["make test"]\n[docs_map]\n"src/**" = ["docs/a.md"]\n')
        config = dw_config.load_config(path)
        self.assertEqual(config.get("gate.commands"), ["make test"])
        self.assertEqual(config.get("gate.lint"), [])
        self.assertEqual(config.get("docs_map"), {"src/**": ["docs/a.md"]})

    def test_finds_config_walking_up_from_subdirectory(self) -> None:
        import dw_config

        path = write_config(self.root, "")
        nested = self.root / "src" / "pkg"
        nested.mkdir(parents=True)
        self.assertEqual(dw_config.find_config(nested), path.resolve())

    def test_cli_finds_config_from_cwd(self) -> None:
        write_config(self.root, '[project]\nname = "demo"\n')
        nested = self.root / "a" / "b"
        nested.mkdir(parents=True)
        result = run_script("dw_config.py", ["--get", "project.name"], cwd=nested)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout.strip(), "demo")

    def test_cli_get_json(self) -> None:
        write_config(self.root, '[gate]\ncommands = ["pytest -q"]\n')
        result = run_script("dw_config.py", ["--get", "gate.commands", "--json"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["pytest -q"])

    def test_cli_full_json(self) -> None:
        write_config(self.root, "")
        result = run_script("dw_config.py", ["--json"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(json.loads(result.stdout)["paths"]["traceability"], "docs/_shared/traceability.md")

    def test_unknown_keys_warn_but_succeed(self) -> None:
        write_config(self.root, "[gate]\ncommandz = []\n[extra]\nx = 1\n")
        result = run_script("dw_config.py", ["--json"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn("unknown key gate.commandz", result.stderr)
        self.assertIn("unknown section [extra]", result.stderr)
        self.assertNotIn("commandz", json.loads(result.stdout)["gate"])

    def test_invalid_toml_exits_2(self) -> None:
        write_config(self.root, "[gate\ncommands = \n")
        result = run_script("dw_config.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("invalid TOML", result.stderr)

    def test_wrong_type_exits_2(self) -> None:
        write_config(self.root, '[project]\nmax_file_lines = "many"\n')
        result = run_script("dw_config.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("project.max_file_lines", result.stderr)

    def test_missing_config_exits_2(self) -> None:
        result = run_script("dw_config.py", [], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("no .claude/dev-workflow.toml found", result.stderr)

    def test_unknown_get_key_exits_2(self) -> None:
        write_config(self.root, "")
        result = run_script("dw_config.py", ["--get", "gate.nope"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)

    def test_example_config_matches_defaults(self) -> None:
        import dw_config

        example = (TEMPLATES_DIR / "dev-workflow.example.toml").read_text(encoding="utf-8")
        config = dw_config.load_config(write_config(self.root, example))
        self.assertEqual(config.warnings, [])
        expected = dict(dw_config.DEFAULTS)
        expected["project"] = {**dw_config.DEFAULTS["project"], "name": "my-repo"}
        self.assertEqual(config.data, expected)


if __name__ == "__main__":
    unittest.main()
