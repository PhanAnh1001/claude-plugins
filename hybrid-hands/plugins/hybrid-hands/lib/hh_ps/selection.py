"""List running children first, then every finished child newest first."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Optional, TypeVar

from .constants import SUMMARY_BAD_TEXT, SUMMARY_OK_TEXT

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
    return Selection([item.payload for item in running + done])
