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


EXTERNAL_RULES = """---
Luật bàn giao cho phiên phụ {name} (hand ngoài, chạy không có người trực):
- Không hỏi người dùng; việc ngoài phạm vi thì dừng phần đó và ghi lại trong báo cáo.
- Chỉ làm trong thư mục làm việc hiện tại; không ghi file ngoài thư mục làm việc.
- Báo cáo cuối của lượt chạy mở đầu bằng khối "## Tóm tắt" tối đa 15 dòng: kết quả (xong / xong một phần / bị chặn), file đã đổi, kiểm chứng đã chạy và kết quả thật, việc còn lại. side-session tự chép báo cáo này thành file bàn giao cho brain.
"""


def build_prompt(user_prompt: str, name: str, handoff: Path, brain: str,
                 external: bool = False, account: str = "v1", main: bool = False,
                 model: str = "", effort: str = "") -> str:
    if external:
        return f"{user_prompt.rstrip()}\n\n{EXTERNAL_RULES.format(name=name).strip()}\n"
    relpath = (C.MAIN_CLAUDE_TEMPLATE_RELPATH if main else
               C.TEMPLATE_RELPATH if account == "v1" else C.CLAUDE_ACCOUNT_TEMPLATE_RELPATH)
    path = PLUGIN_ROOT / relpath
    if not path.is_file():
        raise ValueError(f"side-session: thiếu template {relpath} (dependency gói C)")
    model = model or C.CLAUDE_MODEL_DEFAULT
    tpl = (path.read_text(encoding="utf-8").replace(C.CLAUDE_ACCOUNT_PLACEHOLDER, account)
           .replace(C.CLAUDE_MODEL_LABEL_PLACEHOLDER, C.CLAUDE_MODEL_LABELS.get(model, model))
           .replace(C.CLAUDE_EFFORT_PLACEHOLDER, effort or C.CLAUDE_EFFORT_DEFAULT))
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
