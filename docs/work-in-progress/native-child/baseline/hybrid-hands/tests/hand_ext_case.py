"""Shared setup for hand-ext tests.

The suite can run inside Codex's seatbelt, which exports CODEX_SANDBOX=seatbelt to every
child process. Tests must see the normal outside-sandbox environment; only tests that
exercise the nested seatbelt case set the variable themselves with mock.patch.dict.
"""
from __future__ import annotations

import os
import unittest

ISOLATED_ENV = ("CODEX_SANDBOX", "CODEX_THREAD_ID", "PASEO_AGENT_ID",
                "HYBRID_HANDS_HAND_SCOPE")


class HandExtTestCase(unittest.TestCase):
    """Isolate inherited sandbox and parent/scope identifiers, then restore them."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._inherited_env = {key: os.environ.pop(key, None) for key in ISOLATED_ENV}
        cls.addClassCleanup(cls._restore_sandbox)

    @classmethod
    def _restore_sandbox(cls) -> None:
        for key, value in cls._inherited_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
