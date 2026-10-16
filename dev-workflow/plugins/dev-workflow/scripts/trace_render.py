"""Render a TraceReport as Vietnamese markdown (traceability.md) or JSON (used by trace_check.py)."""
from __future__ import annotations

import datetime as dt
import json

from trace_report import TaskLink, TraceReport

GENERATOR = "dev-workflow trace_check.py"
EMPTY_CELL = "—"
NONE_ITEM = "- Không có."


def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in values) if values else EMPTY_CELL


def _task_cell(tasks: list[TaskLink]) -> str:
    if not tasks:
        return EMPTY_CELL
    return ", ".join(f"`{t.task_id}`" + (" (xong)" if t.done else "") for t in tasks)


def _or_none(lines: list[str]) -> list[str]:
    return lines or [NONE_ITEM]


def _required(types: list[str]) -> str:
    return ", ".join(types) or "không"


def _summary_lines(report: TraceReport) -> list[str]:
    by_type = ", ".join(f"{k}: {v}" for k, v in sorted(report.count_by_type().items())) or "không có"
    todo = (
        "Không có việc cần làm: mọi ID bắt buộc đã có task và test, không có ID trùng."
        if report.ok
        else "Sửa ID trùng và bổ sung task (`covers:` trong plan) hoặc test (ID trong tên test/comment) "
             "cho các ID ở mục 2, hoặc ghi miễn trừ có lý do vào `[trace].waivers`."
    )
    return [
        "## Tóm tắt",
        "",
        f"- **Nguồn:** sinh tự động bởi `{GENERATOR}` từ SRS, plan và test. Không sửa tay; chạy lại với `--write`.",
        f"- **Số ID:** {len(report.rows)} ({by_type}).",
        f"- **Thiếu task:** {len(report.missing_task)} (bắt buộc với: {_required(report.require_task_types)}).",
        f"- **Thiếu test:** {len(report.missing_test)} (bắt buộc với: {_required(report.require_test_types)}).",
        f"- **ID định nghĩa trùng** (lỗi): {len(report.duplicates)}.",
        f"- **Miễn trừ:** {len(report.waived)}.",
        f"- **ID mồ côi** (được tham chiếu nhưng không định nghĩa): {len(report.orphans)}.",
        f"- **ID sai định dạng** (cảnh báo): {len(report.malformed)}.",
        f"- **Việc cần làm:** {todo}",
    ]


def _matrix_lines(report: TraceReport) -> list[str]:
    lines = ["## 1. Ma trận truy vết", "", "| ID | Định nghĩa | Task | Test |", "|---|---|---|---|"]
    for row in report.rows:
        lines.append(
            f"| `{row.id}` | {_code_list(row.defined_at)} | {_task_cell(row.tasks)} | {_code_list(row.tests)} |"
        )
    if not report.rows:
        lines.append(f"| {EMPTY_CELL} | {EMPTY_CELL} | {EMPTY_CELL} | {EMPTY_CELL} |")
    return lines


def _gap_lines(report: TraceReport) -> list[str]:
    duplicates = [f"- `{i}`: {_code_list(locs)}" for i, locs in report.duplicates.items()]
    return [
        "## 2. Lỗi và thiếu liên kết", "",
        "### 2.1 Thiếu task", "", *_or_none([f"- `{i}`" for i in report.missing_task]), "",
        "### 2.2 Thiếu test", "", *_or_none([f"- `{i}`" for i in report.missing_test]), "",
        "### 2.3 ID định nghĩa trùng", "", *_or_none(duplicates),
    ]


def _waiver_lines(report: TraceReport) -> list[str]:
    lines = ["## 3. Miễn trừ", ""]
    if report.waived:
        lines += ["| ID | Lý do |", "|---|---|"]
        lines += [f"| `{i}` | {reason} |" for i, reason in report.waived.items()]
    else:
        lines.append(NONE_ITEM)
    if report.unknown_waivers:
        lines += ["", "Miễn trừ cho ID không tồn tại (cần xoá khỏi `[trace].waivers`):", ""]
        lines += [f"- `{i}`: {reason}" for i, reason in report.unknown_waivers.items()]
    return lines


def _warning_lines(report: TraceReport) -> list[str]:
    orphans = [f"- `{i}`: {_code_list(locs)}" for i, locs in report.orphans.items()]
    malformed = [f"- `{text}`: `{location}`" for text, location in report.malformed]
    return [
        "## 4. Cảnh báo", "",
        "### 4.1 ID mồ côi", "", *_or_none(orphans), "",
        "### 4.2 ID sai định dạng", "",
        "Định dạng đúng: `<TYPE>-<feature>-NNN` (feature kebab-case chữ thường, NNN 2–3 chữ số).", "",
        *_or_none(malformed),
    ]


def render_markdown(report: TraceReport, today: dt.date | None = None) -> str:
    date = (today or dt.date.today()).isoformat()
    front = ["---", "id: traceability", "title: Ma trận truy vết", f"generated-by: {GENERATOR}",
             f"last-reviewed: {date}", "---", "", "# Ma trận truy vết", ""]
    sections = [_summary_lines(report), _matrix_lines(report), _gap_lines(report),
                _waiver_lines(report), _warning_lines(report)]
    body: list[str] = []
    for section in sections:
        body += [*section, ""]
    return "\n".join(front + body).rstrip("\n") + "\n"


def render_json(report: TraceReport) -> str:
    payload = {
        "ok": report.ok,
        "summary": {
            "ids": len(report.rows),
            "by_type": report.count_by_type(),
            "missing_task": report.missing_task,
            "missing_test": report.missing_test,
            "duplicates": sorted(report.duplicates),
            "waived": sorted(report.waived),
            "orphans": sorted(report.orphans),
            "malformed": len(report.malformed),
        },
        "rows": [
            {
                "id": row.id,
                "type": row.id_type,
                "defined_at": row.defined_at,
                "tasks": [{"id": t.task_id, "done": t.done} for t in row.tasks],
                "tests": row.tests,
                "missing_task": row.missing_task,
                "missing_test": row.missing_test,
                "waiver": row.waiver,
            }
            for row in report.rows
        ],
        "duplicates": report.duplicates,
        "waivers": report.waived,
        "unknown_waivers": report.unknown_waivers,
        "orphans": report.orphans,
        "malformed": [{"text": text, "location": location} for text, location in report.malformed],
        "errors": report.errors,
        "warnings": report.warnings,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
