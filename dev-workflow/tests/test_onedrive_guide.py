"""Tests for `dw onedrive guide` (no config, no network)."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _support
import onedrive

NO_NETWORK = mock.Mock(side_effect=AssertionError("network used"))
MISSING_CONFIG = "/nonexistent/dev-workflow.toml"


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = onedrive.main(["--config", MISSING_CONFIG, *argv], transport=NO_NETWORK)
    return code, out.getvalue()


@_support.requires_tomllib
class GuideTest(unittest.TestCase):
    def test_guide_prints_without_config(self) -> None:
        code, text = run_cli("guide")
        self.assertEqual(code, 0)
        self.assertIn("Add shortcut to My files", text)

    def test_unknown_topic_exits_2(self) -> None:
        code, text = run_cli("guide", "--topic", "nope")
        self.assertEqual(code, 2)
        self.assertIn("macos-sync", text)


if __name__ == "__main__":
    unittest.main()
