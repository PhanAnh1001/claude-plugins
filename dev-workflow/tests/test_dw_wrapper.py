"""Tests for scripts/dw (entry point) and scripts/_pick_python.sh (interpreter choice)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import SCRIPTS_DIR, SUBPROCESS_TIMEOUT_SECONDS, write_config, write_file

DW = SCRIPTS_DIR / "dw"
HOOK = SCRIPTS_DIR / "session-start.sh"
BASH = "/bin/bash"  # absolute so a fake PATH cannot hide it
EXIT_OK = 0
EXIT_MISSING_LINKS = 1
EXIT_ERROR = 2
UV_COMMAND = "uv run --no-project --python 3.11 python"


def run(command: list[str], cwd: Path, path: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
    )


def make_stub(directory: Path, name: str, body: str) -> None:
    stub = write_file(directory, name, f"#!/bin/sh\n{body}\n")
    stub.chmod(0o755)


def real_python_available() -> bool:
    return run([BASH, str(DW), "python"], cwd=SCRIPTS_DIR).returncode == EXIT_OK


class DwWithRealPythonTest(unittest.TestCase):
    def setUp(self) -> None:
        if not real_python_available():
            self.skipTest("no Python >= 3.11 or uv on PATH")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_config_json_with_explicit_path(self) -> None:
        config = write_config(self.root, '[gate]\ncommands = ["make test"]\n')
        result = run([str(DW), "config", "--json", "--config", str(config)], cwd=SCRIPTS_DIR)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["gate"]["commands"], ["make test"])
        self.assertEqual(data["frontend"]["checks"], [])

    def test_config_get_from_cwd(self) -> None:
        write_config(self.root, '[project]\nname = "demo"\n')
        result = run([str(DW), "config", "--get", "project.name"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout.strip(), "demo")

    def test_config_error_exit_code_is_passed_through(self) -> None:
        result = run([str(DW), "config"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_trace_exit_code_is_passed_through(self) -> None:
        write_config(self.root, '[paths]\nsrs = ["srs/*.md"]\n')
        write_file(self.root, "srs/spec.md", "| ID | x |\n|---|---|\n| FR-a-001 | y |\n")
        result = run([str(DW), "trace", "--format", "json"], cwd=self.root)
        self.assertEqual(result.returncode, EXIT_MISSING_LINKS, result.stderr)
        self.assertEqual(json.loads(result.stdout)["summary"]["missing_test"], ["FR-a-001"])


class DwInterpreterChoiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self._tmp.name).resolve() / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_no_interpreter_exits_2_with_message(self) -> None:
        make_stub(self.bin, "python3", "exit 1")  # an old python3 without tomllib
        result = run([BASH, str(DW), "config", "--json"], cwd=self.bin, path=str(self.bin))
        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertIn("no Python >= 3.11", result.stderr)

    def test_falls_back_to_uv(self) -> None:
        make_stub(self.bin, "uv", "exit 0")
        result = run([BASH, str(DW), "python"], cwd=self.bin, path=str(self.bin))
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout.strip(), UV_COMMAND)

    def test_prefers_candidate_with_tomllib(self) -> None:
        make_stub(self.bin, "python3", "exit 1")
        make_stub(self.bin, "python3.12", "exit 0")
        make_stub(self.bin, "uv", "exit 0")
        result = run([BASH, str(DW), "python"], cwd=self.bin, path=str(self.bin))
        self.assertEqual(result.stdout.strip(), "python3.12")

    def test_unknown_subcommand_exits_2(self) -> None:
        result = run([BASH, str(DW), "bogus"], cwd=self.bin)
        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertIn("usage: dw", result.stderr)

    def test_hook_warns_without_interpreter_and_exits_0(self) -> None:
        project = Path(self._tmp.name).resolve() / "project"
        write_config(project, "")
        env_path = str(self.bin)
        result = subprocess.run(
            [BASH, str(HOOK)], env={"PATH": env_path, "CLAUDE_PROJECT_DIR": str(project)},
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS, check=False,
        )
        self.assertEqual(result.returncode, EXIT_OK)
        self.assertIn("scripts/dw\" config", result.stdout)
        self.assertIn("no Python >= 3.11 or uv", result.stdout)

    def test_dw_is_executable(self) -> None:
        self.assertTrue(os.access(DW, os.X_OK))


if __name__ == "__main__":
    unittest.main()
