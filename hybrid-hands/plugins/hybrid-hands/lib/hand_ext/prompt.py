"""Build the hand prompt: shared preamble + BRIEF."""
from __future__ import annotations

import sys
from pathlib import Path

from .config import PLUGIN_DIR
from .constants import BRIEF_HEADER, PREAMBLE_RELPATH

STDIN_MARK = "-"


def read_brief(src: str) -> str:
    return sys.stdin.read() if src == STDIN_MARK else Path(src).read_text(encoding="utf-8")


def build_prompt(brief: str) -> str:
    preamble = (PLUGIN_DIR / PREAMBLE_RELPATH).read_text(encoding="utf-8")
    return preamble.rstrip() + BRIEF_HEADER + brief.strip() + "\n"
