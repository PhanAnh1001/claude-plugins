"""Terminal display width of text, used to align `hh-ps` columns."""
from __future__ import annotations

import re
import unicodedata

from .constants import ELLIPSIS

ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")
# East Asian Width classes that take two terminal cells.
WIDE_CLASSES = ("W", "F")
WIDE_CELLS = 2
NARROW_CELLS = 1


def _char_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    if unicodedata.east_asian_width(char) in WIDE_CLASSES:
        return WIDE_CELLS
    return NARROW_CELLS


def display_width(text: str) -> int:
    """Cells `text` takes in a terminal; ANSI colour codes count as zero."""
    plain = unicodedata.normalize("NFC", ANSI_ESCAPE.sub("", text))
    return sum(_char_width(char) for char in plain)


def truncate_display(text: str, limit: int, ellipsis: str = ELLIPSIS) -> str:
    """Cut `text` to at most `limit` display cells, ending with `ellipsis`."""
    value = unicodedata.normalize("NFC", text)
    if display_width(value) <= limit:
        return value
    budget = limit - display_width(ellipsis)
    kept, used = [], 0
    for char in value:
        cells = _char_width(char)
        if used + cells > budget:
            break
        kept.append(char)
        used += cells
    return "".join(kept) + ellipsis


def pad_right(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def pad_left(text: str, width: int) -> str:
    return " " * max(0, width - display_width(text)) + text
