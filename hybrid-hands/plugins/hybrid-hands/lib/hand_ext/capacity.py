"""Pure helpers for the dsh 429 capacity branch (kept apart from the run orchestration)."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .backends.base import Status, is_capacity_error
from .constants import DSH_CAPACITY_MAX_CONTINUATIONS
from .runner import RunOutcome

CONTINUATION_MARK = "đã có patch, làm tiếp"
CONTINUATION_BLOCK = (
    "\n\n## GHI CHÚ CHẠY TIẾP\n\n" + CONTINUATION_MARK
    + " phần còn lại; không làm lại từ đầu.\n")


def is_capacity_failure(outcome: RunOutcome) -> bool:
    return (outcome.status is Status.FAILED
            and is_capacity_error("\n".join(outcome.errors or [])))


def continuation_prompt(prompt: str) -> str:
    return prompt.rstrip() + CONTINUATION_BLOCK


def report_lines(branch: str, changed: int, threshold: int, wait_s: int,
                 continuations: int, result: str,
                 patch_path: Optional[Path]) -> List[str]:
    out = [
        "## Dự phòng 429 quá tải",
        f"- Nhánh: {branch}",
        f"- Patch dsh: {changed} dòng thêm+xoá (ngưỡng {threshold})",
        f"- Chờ: {wait_s} s/lần; chạy tiếp: {continuations}/"
        f"{DSH_CAPACITY_MAX_CONTINUATIONS} lần",
        f"- Kết quả: {result}",
    ]
    if patch_path is not None:
        out.append(f"- Patch: `{patch_path}`")
    return out
