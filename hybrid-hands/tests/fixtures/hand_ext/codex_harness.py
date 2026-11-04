"""Shared setup for hand-ext tests: temp project + CODEX_HOME + fake codex on env."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import List, Tuple

FIXTURES = Path(__file__).resolve().parent
PL = FIXTURES.parents[2] / "plugins" / "hybrid-hands"
sys.path.insert(0, str(PL / "lib"))

from hand_ext import cli  # noqa: E402

FAKE_CODEX = FIXTURES / "codex_fake.py"
SECRET = "sk-test-SECRET-should-never-leak"


class Sandbox:
    """Temp project dir (non-git: root = dir) with config, CODEX_HOME and env overrides."""

    def __init__(self, order: List[str], logged_in: bool = True, extra: dict = None) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="hand-ext-"))
        self.home = self.dir / "codex-home"
        self.home.mkdir()
        if logged_in:
            (self.home / "auth.json").write_text(json.dumps(
                {"auth_mode": "chatgpt", "tokens": {"access_token": SECRET}}))
        self.log = self.dir / "fake.log"
        section = {"order": order, "backends": {"codex": {"home": str(self.home)}}}
        section.update(extra or {})
        (self.dir / ".claude").mkdir()
        (self.dir / ".claude" / "hybrid-hands.json").write_text(json.dumps({"ext_hand": section}))
        self.brief = self.dir / "brief.md"
        self.brief.write_text("MỤC TIÊU: thử\n")
        self._saved = dict(os.environ)
        os.environ.update({"HAND_EXT_CODEX_BIN": str(FAKE_CODEX), "FAKE_CODEX_LOG": str(self.log),
                           "OPENAI_API_KEY": SECRET, "CODEX_API_KEY": SECRET})

    def scenario(self, name: str) -> None:
        os.environ["FAKE_CODEX_SCENARIO"] = name

    def cli(self, *args: str) -> Tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(args) + ["--cwd", str(self.dir)])
        return code, out.getvalue(), err.getvalue()

    def ledger(self) -> list:
        path = self.dir / "output" / "llm" / "hand_usage.json"
        return json.loads(path.read_text()) if path.is_file() else []

    def quota(self) -> dict:
        path = self.dir / "output" / "llm" / "hand_quota.json"
        return json.loads(path.read_text()) if path.is_file() else {}

    def close(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved)
        shutil.rmtree(self.dir, ignore_errors=True)
