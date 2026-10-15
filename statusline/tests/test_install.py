"""Tests for scripts/install.sh and the shim it writes, always on a temporary CLAUDE_HOME."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from _support import PLUGIN_ROOT, SCRIPTS_DIR, clean_env, run_bash

INSTALL = SCRIPTS_DIR / "install.sh"
SHIM_NAME = "statusline-command.sh"
SETTINGS_NAME = "settings.json"
SHIM_MARKER = "statusline-plugin-shim"
BACKUP_PREFIX = SHIM_NAME + ".bak-"
OLD_SCRIPT = "#!/bin/bash\necho old status line\n"
SETTINGS_MODE = 0o600
OTHER_SETTINGS = {
    "model": "opus",
    "permissions": {"allow": ["Bash(ls:*)"], "deny": []},
    "enabledPlugins": {"statusline@statusline-local": True},
    "statusLine": {"type": "command", "command": "bash /somewhere/else.sh", "padding": 1},
}
PYTHON_BACKEND = {"STATUSLINE_JSON_BACKEND": "python"}
EXIT_ERROR = 1
NOT_FOUND_HINT = "statusline plugin not found"
STATUS_PAYLOAD = json.dumps({"model": {"display_name": "Opus"}, "cwd": "/"})
EXPECTED_LINES = 3


class InstallTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "claude-home"
        self.home.mkdir()
        self.shim = self.home / SHIM_NAME
        self.settings = self.home / SETTINGS_NAME

    # --- helpers ---

    def install(self, *args: str, extra_env: dict | None = None):
        env = clean_env(CLAUDE_HOME=str(self.home), **(extra_env or {}))
        return run_bash(INSTALL, list(args), env)

    def wanted_command(self) -> str:
        return f'bash "{self.shim}"'

    def write_settings(self, document: dict) -> None:
        self.settings.write_text(json.dumps(document, indent=4), encoding="utf-8")
        self.settings.chmod(SETTINGS_MODE)

    def read_settings(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def backups(self) -> list[Path]:
        return sorted(self.home.glob(BACKUP_PREFIX + "*"))

    def snapshot(self) -> dict[str, bytes]:
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def prepare_old_setup(self) -> None:
        self.shim.write_text(OLD_SCRIPT, encoding="utf-8")
        self.write_settings(OTHER_SETTINGS)

    def assert_ok(self, result) -> None:
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def assert_installed(self) -> None:
        self.assertIn(SHIM_MARKER, self.shim.read_text(encoding="utf-8"))
        document = self.read_settings()
        expected_status = {**OTHER_SETTINGS["statusLine"], "type": "command", "command": self.wanted_command()}
        self.assertEqual(document["statusLine"], expected_status)
        for key in ("model", "permissions", "enabledPlugins"):
            self.assertEqual(document[key], OTHER_SETTINGS[key])
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode), SETTINGS_MODE)

    # --- install ---

    def test_first_install_backs_up_writes_shim_and_settings(self) -> None:
        self.prepare_old_setup()
        self.assert_ok(self.install())
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), OLD_SCRIPT)
        self.assert_installed()

    def test_first_install_with_python_backend(self) -> None:
        self.prepare_old_setup()
        self.assert_ok(self.install(extra_env=PYTHON_BACKEND))
        self.assert_installed()

    def test_second_run_changes_nothing(self) -> None:
        self.prepare_old_setup()
        self.assert_ok(self.install())
        before = self.snapshot()
        settings_mtime = self.settings.stat().st_mtime_ns
        result = self.install()
        self.assert_ok(result)
        self.assertIn("nothing to do", result.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.settings.stat().st_mtime_ns, settings_mtime)

    def test_install_on_empty_home_creates_settings(self) -> None:
        self.assert_ok(self.install())
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.read_settings(), {"statusLine": {"type": "command", "command": self.wanted_command()}})

    def test_dry_run_writes_nothing(self) -> None:
        self.prepare_old_setup()
        before = self.snapshot()
        result = self.install("--dry-run")
        self.assert_ok(result)
        self.assertIn("would back up", result.stdout)
        self.assertIn("would set statusLine", result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_settings_is_left_untouched(self) -> None:
        self.settings.write_text("{not json", encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "{not json")

    def test_symlinked_settings_stays_a_symlink(self) -> None:
        real = self.home / "dotfiles-settings.json"
        real.write_text(json.dumps({"model": "opus"}), encoding="utf-8")
        self.settings.symlink_to(real.name)
        self.assert_ok(self.install())
        self.assertTrue(self.settings.is_symlink())
        self.assertEqual(json.loads(real.read_text(encoding="utf-8"))["model"], "opus")
        self.assertIn("statusLine", json.loads(real.read_text(encoding="utf-8")))

    # --- uninstall ---

    def test_uninstall_restores_backup(self) -> None:
        self.prepare_old_setup()
        self.assert_ok(self.install())
        self.assert_ok(self.install("--uninstall"))
        self.assertEqual(self.shim.read_text(encoding="utf-8"), OLD_SCRIPT)
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.read_settings()["statusLine"]["command"], self.wanted_command())
        self.assertIn("nothing to do", self.install("--uninstall").stdout)

    def test_uninstall_without_backup_removes_shim_and_status_line(self) -> None:
        self.write_settings({"model": "opus"})
        self.assert_ok(self.install())
        self.assert_ok(self.install("--uninstall", extra_env=PYTHON_BACKEND))
        self.assertFalse(self.shim.exists())
        self.assertEqual(self.read_settings(), {"model": "opus"})

    def test_uninstall_dry_run_writes_nothing(self) -> None:
        self.prepare_old_setup()
        self.assert_ok(self.install())
        before = self.snapshot()
        result = self.install("--uninstall", "--dry-run")
        self.assert_ok(result)
        self.assertIn("would restore", result.stdout)
        self.assertEqual(self.snapshot(), before)

    # --- shim ---

    def write_installed_plugins(self, key: str, install_path: Path) -> None:
        plugins_dir = self.home / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        document = {"version": 2, "plugins": {key: [{"scope": "user", "installPath": str(install_path)}]}}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(document), encoding="utf-8")

    def run_shim(self, extra_env: dict | None = None):
        env = clean_env(HOME=str(self.home.parent), **(extra_env or {}))
        return run_bash(self.shim, [], env, stdin=STATUS_PAYLOAD, cwd=self.home)

    def test_shim_runs_installed_plugin(self) -> None:
        self.assert_ok(self.install())
        self.write_installed_plugins("statusline@statusline-local", PLUGIN_ROOT)
        result = self.run_shim()
        self.assert_ok(result)
        self.assertEqual(len(result.stdout.split("\n")), EXPECTED_LINES)
        self.assertIn("Opus", result.stdout)
        self.assertTrue((self.home / ".statusline-cache.json").exists())

    def test_shim_finds_plugin_from_other_marketplace_name(self) -> None:
        self.assert_ok(self.install())
        self.write_installed_plugins("statusline@elsewhere", PLUGIN_ROOT)
        result = self.run_shim()
        self.assert_ok(result)
        self.assertIn("Opus", result.stdout)

    def test_shim_without_plugin_prints_hint(self) -> None:
        self.assert_ok(self.install())
        result = self.run_shim()
        self.assert_ok(result)
        self.assertTrue(result.stdout.startswith(NOT_FOUND_HINT))

    def test_scripts_are_executable(self) -> None:
        for name in ("install.sh", "statusline.sh", "last-skill.sh"):
            with self.subTest(script=name):
                self.assertTrue(os.access(SCRIPTS_DIR / name, os.X_OK))


if __name__ == "__main__":
    unittest.main()
