"""Column layout for the `hh-ps` text tree.

Session, side-session and child rows share one table: the first column counts
the tree prefix and the mark, so the size column (`ctx`/`out`) starts at the
same display column at every depth. Padding is computed on plain text and
colour is applied afterwards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .textwidth import display_width

COLUMN_GAP = "  "
GROUP_TREE = "tree"

Painter = Callable[[str, Optional[str]], str]


@dataclass
class Cell:
    text: str = ""
    color_key: Optional[str] = None
    align_right: bool = False
    glue: bool = False

    def __post_init__(self) -> None:
        self.text = str(self.text or "")  # missing fields render as an empty cell


@dataclass
class Line:
    """One tree row: `prefix` is the branch art, `cells[0]` the first column.

    `group` None means a plain heading printed as `prefix + text` unpadded.
    `icon` is a coloured glyph printed before the first cell.
    """
    prefix: str
    cells: List[Cell] = field(default_factory=list)
    group: Optional[str] = None
    icon: Optional[Cell] = None

    def nested(self, outer: str) -> "Line":
        return Line(outer + self.prefix, self.cells, self.group, self.icon)


def _lead(line: Line) -> str:
    icon = f"{line.icon.text} " if line.icon else ""
    return line.prefix + icon + line.cells[0].text


def _widths(lines: List[Line]) -> List[int]:
    count = max(len(line.cells) for line in lines)
    widths = [0] * count
    for line in lines:
        widths[0] = max(widths[0], display_width(_lead(line)))
        for index, cell in enumerate(line.cells[1:], start=1):
            widths[index] = max(widths[index], display_width(cell.text))
    return widths


def _render_line(line: Line, widths: List[int], paint: Painter) -> str:
    icon = f"{paint(line.icon.text, line.icon.color_key)} " if line.icon else ""
    first = line.cells[0]
    lead_pad = " " * max(0, widths[0] - display_width(_lead(line)))
    parts = [line.prefix + icon + paint(first.text, first.color_key) + lead_pad]
    for index, width in enumerate(widths[1:], start=1):
        if not width:
            continue  # column empty in every row of the group
        cell = line.cells[index] if index < len(line.cells) else Cell()
        painted = paint(cell.text, cell.color_key) if cell.text else ""
        # Pad by the plain width so colour codes never count as cells.
        pad = " " * max(0, width - display_width(cell.text))
        piece = pad + painted if cell.align_right else painted + pad
        # `glue` cells (the `|` separators of the token block) skip COLUMN_GAP.
        if cell.glue and parts:
            parts[-1] += piece
        else:
            parts.append(piece)
    return COLUMN_GAP.join(parts).rstrip()


def render_lines(lines: List[Line], paint: Painter) -> List[str]:
    groups: Dict[str, List[Line]] = {}
    for line in lines:
        if line.group is not None:
            groups.setdefault(line.group, []).append(line)
    widths = {name: _widths(members) for name, members in groups.items()}
    out = []
    for line in lines:
        if line.group is None:
            out.append(line.prefix + (line.cells[0].text if line.cells else ""))
        else:
            out.append(_render_line(line, widths[line.group], paint))
    return out
