"""Shared setup for hand-ext tests.

The suite can run inside Codex's seatbelt, which exports CODEX_SANDBOX=seatbelt to every
child process. Tests must see the normal outside-sandbox environment; only tests that
exercise the nested seatbelt case set the variable themselves with mock.patch.dict.
"""
from __future__ import annotations

import os
import unittest

SANDBOX_ENV = "CODEX_SANDBOX"


class HandExtTestCase(unittest.TestCase):
    """Strip an inherited CODEX_SANDBOX for the lifetime of each test class."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._inherited_sandbox = os.environ.pop(SANDBOX_ENV, None)
        cls.addClassCleanup(cls._restore_sandbox)

    @classmethod
    def _restore_sandbox(cls) -> None:
        if cls._inherited_sandbox is None:
            os.environ.pop(SANDBOX_ENV, None)
        else:
            os.environ[SANDBOX_ENV] = cls._inherited_sandbox
