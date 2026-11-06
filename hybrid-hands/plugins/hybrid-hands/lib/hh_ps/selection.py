"""Which children of a session are listed: the rule shared with hh-tree-pane.

Running children first (in source order), then up to RECENT_FINISHED_SHOWN
finished or failed children by end time, newest first; the rest are counted
for a `+N xong · M lỗi` summary. hooks/tree.ts mirrors this; change both.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Optional, TypeVar

from .constants import RECENT_FINISHED_SHOWN, SUMMARY_BAD_TEXT, SUMMARY_OK_TEXT

T = TypeVar("T")


@dataclass
class ChildItem(Generic[T]):
    payload: T
    running: bool
    bad: bool
    end: Optional[float]


@dataclass
class Selection(Generic[T]):
    shown: List[T]
    hidden_ok: int = 0
    hidden_bad: int = 0

    @property
    def summary(self) -> str:
        """`+N xong · M lỗi`, dropping zero parts; empty when nothing is hidden."""
        parts = []
        if self.hidden_ok:
            parts.append(f"{self.hidden_ok} {SUMMARY_OK_TEXT}")
        if self.hidden_bad:
            parts.append(f"{self.hidden_bad} {SUMMARY_BAD_TEXT}")
        return f"+{' · '.join(parts)}" if parts else ""


def _end_key(item: ChildItem) -> float:
    # A child without a known end (a lost run) sorts after every dated one.
    return item.end if item.end is not None else float("-inf")


def select_children(items: List[ChildItem[T]], full: bool = False) -> Selection[T]:
    running = [item for item in items if item.running]
    done = sorted((item for item in items if not item.running), key=_end_key,
                  reverse=True)
    if full:
        return Selection([item.payload for item in running + done])
    kept, rest = done[:RECENT_FINISHED_SHOWN], done[RECENT_FINISHED_SHOWN:]
    bad = sum(1 for item in rest if item.bad)
    return Selection([item.payload for item in running + kept], len(rest) - bad, bad)
