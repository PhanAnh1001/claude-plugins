"""Tests for scripts/od_local.py through the onedrive.py CLI (temporary folders, no network)."""
from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import _support
import onedrive

NO_NETWORK = mock.Mock(side_effect=AssertionError("network used"))


class LocalBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.synced = self.base / "OneDrive-Org" / "Team"
        self.synced.mkdir(parents=True)
        self.config = _support.write_config(
            self.base, f'[onedrive]\nclient_id = ""\nfolders = {{ team = "{self.synced}" }}\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *argv: str) -> tuple[int, str, bytes]:
        out, err = io.StringIO(), io.StringIO()
        buffer = io.BytesIO()
        out.buffer = buffer  # type: ignore[attr-defined]
        with redirect_stdout(out), redirect_stderr(err):
            code = onedrive.main(["--config", str(self.config), *argv], transport=NO_NETWORK)
        return code, out.getvalue() + err.getvalue(), buffer.getvalue()

    def test_put_ls_get_without_client_id(self) -> None:
        local = _support.write_file(self.base, "a.txt", "one")
        self.assertEqual(self.run_cli("put", str(local), "team:Kế hoạch/", "--mkdir")[0], 0)
        code, text, _ = self.run_cli("put", str(local), "team:Kế hoạch/a.txt")
        self.assertEqual(code, 1)
        self.assertIn("--overwrite", text)
        local.write_text("two")
        self.assertEqual(self.run_cli("put", str(local), "team:Kế hoạch/a.txt", "--overwrite")[0], 0)
        code, text, _ = self.run_cli("ls", "team:Kế hoạch")
        self.assertEqual(code, 0)
        self.assertTrue(text.startswith("f\ta.txt\t3\t"))
        code, _, data = self.run_cli("get", "team:Kế hoạch/a.txt")
        self.assertEqual((code, data), (0, b"two"))
        NO_NETWORK.assert_not_called()

    def test_symlink_leaving_root_is_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (self.synced / "escape").symlink_to(outside)
        local = _support.write_file(self.base, "b.txt", "x")
        code, text, _ = self.run_cli("put", str(local), "team:escape/b.txt")
        self.assertEqual(code, 1)
        self.assertIn("outside the alias folder", text)
        self.assertFalse((outside / "b.txt").exists())

    def test_discover_lists_roots_and_subfolders(self) -> None:
        with mock.patch.dict(os.environ, {"DW_ONEDRIVE_CLOUDSTORAGE_DIR": str(self.base)}):
            code, text, _ = self.run_cli("discover")
        self.assertEqual(code, 0)
        self.assertIn(f"root\t{self.base / 'OneDrive-Org'}", text)
        self.assertIn(f"d\t{self.synced}", text)


if __name__ == "__main__":
    unittest.main()
