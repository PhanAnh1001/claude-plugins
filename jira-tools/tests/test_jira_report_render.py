"""Format hiển thị báo cáo tuần — so sánh chuỗi nguyên văn từng ký tự."""

from __future__ import annotations

from typing import Any

from jira_tools.report_render import (
    Group,
    Item,
    Report,
    Style,
    group_issues,
    render_document,
    render_draft,
    render_report,
)

GROUPS = (
    Group("Nạp tài liệu", (Item("Nạp PDF", ("AILUX-1", "AILUX-2")), Item("Ghi chú không key"))),
    Group("Trợ lý AI", (Item("Trả lời có trích dẫn", ("AILUX-5",)),)),
)


def test_detail_report_format_is_exact() -> None:
    text = render_report("LUXIAN", Report("h", Style.DETAIL, GROUPS))
    assert text == (
        "* Dự án LUXIAN\n"
        "1. Nạp tài liệu\n"
        " - Nạp PDF (AILUX-1, AILUX-2)\n"
        " - Ghi chú không key\n"
        "2. Trợ lý AI\n"
        " - Trả lời có trích dẫn (AILUX-5)"
    )


def test_summary_report_format_has_no_keys() -> None:
    text = render_report("LUXIAN", Report("h", Style.SUMMARY, GROUPS))
    assert text == (
        "LUXIAN\n"
        "1. Nạp tài liệu\n"
        " - Nạp PDF\n"
        " - Ghi chú không key\n"
        "2. Trợ lý AI\n"
        " - Trả lời có trích dẫn"
    )


def test_document_separates_reports_with_headings_and_one_blank_line() -> None:
    reports = [Report("A", Style.SUMMARY, GROUPS[1:]), Report("B", Style.DETAIL, GROUPS[1:])]
    assert render_document("T", reports) == (
        "== A ==\n\nT\n1. Trợ lý AI\n - Trả lời có trích dẫn\n\n"
        "== B ==\n\n* Dự án T\n1. Trợ lý AI\n - Trả lời có trích dẫn (AILUX-5)"
    )


def _issue(key: str, epic_name: str | None, labels: list[str]) -> dict[str, Any]:
    return {"key": key, "summary": f"Việc {key}", "epic_name": epic_name, "labels": labels}


def test_draft_groups_by_epic_then_non_shared_label_then_other() -> None:
    issues = [
        _issue("P-10", None, ["chung"]),
        _issue("P-9", None, ["chung", "ui"]),
        _issue("P-3", "Kho tri thức", ["chung"]),
        _issue("P-4", None, ["chung", "ui"]),
    ]
    grouped = [(name, [i["key"] for i in members]) for name, members in group_issues(issues)]
    assert grouped == [("Kho tri thức", ["P-3"]), ("ui", ["P-4", "P-9"]), ("Khác", ["P-10"])]


def test_render_draft_plan_section_is_exact() -> None:
    data = {
        "title": "T",
        "plan": {"from": "2026-11-06", "to": "2026-11-12", "remaining_hours": 1.5,
                 "issues": [_issue("P-2", "Epic", [])]},
    }
    assert render_draft(data) == (
        "== Báo cáo chi tiết sẽ làm (06/11 – 12/11/2026) ==\n\n"
        "* Dự án T\n1. Epic\n - Việc P-2 (P-2)\n\n"
        "== Báo cáo tóm tắt sẽ làm (06/11 – 12/11/2026) ==\n\n"
        "T\n1. Epic\n - Việc P-2\n\n"
        "Tổng ước lượng còn lại: 1.5 giờ"
    )
