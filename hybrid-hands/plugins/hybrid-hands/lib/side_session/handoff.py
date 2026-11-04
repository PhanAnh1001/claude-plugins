"""Handoff file helpers and prompt assembly."""
from __future__ import annotations

from pathlib import Path

from . import constants as C

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def summary_block(path: Path) -> str | None:
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == C.SUMMARY_HEADING)
    except StopIteration:
        return None
    body: list[str] = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body[: C.SUMMARY_MAX_LINES + 1])  # heading + <= 15 lines


def build_prompt(user_prompt: str, name: str, handoff: Path, brain: str) -> str:
    tpl = (PLUGIN_ROOT / C.TEMPLATE_RELPATH).read_text(encoding="utf-8")
    out_lines = []
    for line in tpl.splitlines():
        if C.BRAIN_LINE_MARKER in line:
            if not brain:
                continue
            line = line.replace(C.BRAIN_LINE_MARKER, "").lstrip()
        out_lines.append(line)
    rules = ("\n".join(out_lines).replace(C.BRAIN_PLACEHOLDER, brain)
             .replace(C.NAME_PLACEHOLDER, name).replace(C.HANDOFF_PLACEHOLDER, str(handoff)))
    return f"{user_prompt.rstrip()}\n\n{rules.strip()}\n"
