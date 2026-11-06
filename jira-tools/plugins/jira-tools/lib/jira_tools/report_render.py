"""Hiển thị báo cáo tuần — hàm thuần, không gọi Jira hay git.

Format cố định (người nhận dán thẳng vào chat/email nên từng ký tự đều quan trọng):

- ``detail``: dòng đầu ``* Dự án <title>``, mỗi mục con `` - <text> (<KEY>, ...)``;
- ``summary``: dòng đầu ``<title>``, mục con `` - <text>`` (không key).

Nhóm đánh số ``1.``, ``2.``…; mục con luôn mở bằng đúng một dấu cách rồi ``- ``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Final

from jira_tools.errors import ConfigError
from jira_tools.report_period import Period, key_sort_value


class Style(str, Enum):
    DETAIL = "detail"
    SUMMARY = "summary"


DETAIL_TITLE_PREFIX: Final = "* Dự án "
ITEM_PREFIX: Final = " - "
#: Nhóm cho issue không có epic và không có label riêng.
OTHER_GROUP: Final = "Khác"
DONE_DETAIL_NAME: Final = "Báo cáo chi tiết đã làm"
DONE_SUMMARY_NAME: Final = "Báo cáo tóm tắt đã làm"
PLAN_DETAIL_NAME: Final = "Báo cáo chi tiết sẽ làm"
PLAN_SUMMARY_NAME: Final = "Báo cáo tóm tắt sẽ làm"
REMAINING_LINE: Final = "Tổng ước lượng còn lại: {hours} giờ"
#: Gạch ngang dài (en dash) giữa hai ngày trong tiêu đề.
RANGE_DASH: Final = " – "


@dataclass(frozen=True)
class Item:
    text: str
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class Group:
    name: str
    items: tuple[Item, ...] = ()


@dataclass(frozen=True)
class Report:
    heading: str
    style: Style
    groups: tuple[Group, ...] = field(default_factory=tuple)


def render_item(item: Item, style: Style) -> str:
    if style is Style.DETAIL and item.keys:
        return f"{ITEM_PREFIX}{item.text} ({', '.join(item.keys)})"
    return f"{ITEM_PREFIX}{item.text}"


def render_report(title: str, report: Report) -> str:
    """Khối báo cáo, không dòng trống bên trong."""
    first = f"{DETAIL_TITLE_PREFIX}{title}" if report.style is Style.DETAIL else title
    lines = [first]
    for number, group in enumerate(report.groups, start=1):
        lines.append(f"{number}. {group.name}")
        lines.extend(render_item(item, report.style) for item in group.items)
    return "\n".join(lines)


def render_document(title: str, reports: Sequence[Report]) -> str:
    """Mỗi báo cáo: ``== heading ==``, dòng trống, khối; giữa hai báo cáo một dòng trống."""
    blocks = [f"== {r.heading} ==\n\n{render_report(title, r)}" for r in reports]
    return "\n\n".join(blocks)


def range_label(period: Period) -> str:
    """``30/10 – 06/11/2026``."""
    return f"{period.start:%d/%m}{RANGE_DASH}{period.end:%d/%m/%Y}"


def common_labels(issues: Sequence[Mapping[str, Any]]) -> set[str]:
    if not issues:
        return set()
    sets = [set(i.get("labels") or ()) for i in issues]
    return set.intersection(*sets)


def group_name(issue: Mapping[str, Any], shared: set[str]) -> str:
    if issue.get("epic_name"):
        return str(issue["epic_name"])
    for label in issue.get("labels") or ():
        if label not in shared:
            return str(label)
    return OTHER_GROUP


def group_issues(issues: Sequence[Mapping[str, Any]]) -> list[tuple[str, list[Mapping]]]:
    """Nhóm theo epic/label; thứ tự nhóm theo key nhỏ nhất, trong nhóm theo key."""
    shared = common_labels(issues)
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for issue in issues:
        groups.setdefault(group_name(issue, shared), []).append(issue)
    for members in groups.values():
        members.sort(key=lambda i: key_sort_value(str(i.get("key", ""))))
    return sorted(groups.items(), key=lambda kv: key_sort_value(str(kv[1][0].get("key", ""))))


def draft_report(heading: str, style: Style, issues: Sequence[Mapping[str, Any]]) -> Report:
    groups = tuple(
        Group(name, tuple(Item(str(i.get("summary", "")), (str(i.get("key", "")),))
                          for i in members))
        for name, members in group_issues(issues)
    )
    return Report(heading, style, groups)


def draft_section(names: tuple[str, str], period: Period,
                  issues: Sequence[Mapping[str, Any]]) -> list[Report]:
    label = range_label(period)
    detail, summary = names
    return [
        draft_report(f"{detail} ({label})", Style.DETAIL, issues),
        draft_report(f"{summary} ({label})", Style.SUMMARY, issues),
    ]


def render_draft(data: Mapping[str, Any]) -> str:
    """Bản nháp máy tạo từ dữ liệu ``--json``; ``plan`` có thêm dòng tổng ước lượng."""
    title = str(data.get("title", ""))
    parts: list[str] = []
    for kind, names in (("done", (DONE_DETAIL_NAME, DONE_SUMMARY_NAME)),
                        ("plan", (PLAN_DETAIL_NAME, PLAN_SUMMARY_NAME))):
        section = data.get(kind)
        if not section:
            continue
        period = Period(date.fromisoformat(section["from"]), date.fromisoformat(section["to"]))
        parts.append(render_document(title, draft_section(names, period, section["issues"])))
        if kind == "plan":
            parts.append(REMAINING_LINE.format(hours=section.get("remaining_hours", 0)))
    return "\n\n".join(parts)


def _parse_item(raw: Mapping[str, Any]) -> Item:
    return Item(str(raw.get("text", "")), tuple(str(k) for k in raw.get("keys") or ()))


def _parse_report(raw: Mapping[str, Any]) -> Report:
    try:
        style = Style(raw.get("style"))
    except ValueError:
        message = f"style phải là detail hoặc summary, nhận: {raw.get('style')!r}"
        raise ConfigError(message) from None
    groups = tuple(
        Group(str(g.get("name", "")), tuple(_parse_item(i) for i in g.get("items") or ()))
        for g in raw.get("groups") or ()
    )
    return Report(str(raw.get("heading", "")), style, groups)


def render_input(data: Any) -> str:
    """Render JSON soạn sẵn ``{"title", "reports": [...]}``; sai cấu trúc thì ``ConfigError``."""
    if not isinstance(data, Mapping) or not isinstance(data.get("reports"), list):
        raise ConfigError('--input phải là object JSON có "title" và mảng "reports"')
    reports = [_parse_report(r) for r in data["reports"]]
    return render_document(str(data.get("title", "")), reports)
