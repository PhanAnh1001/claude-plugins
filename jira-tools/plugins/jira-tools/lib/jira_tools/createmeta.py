"""Createmeta của Jira Server 9: dựng URL, gộp trang và định dạng — không chạm mạng.

Jira 9 **đã gỡ** ``GET /rest/api/2/issue/createmeta?projectKeys=...``. Máy chủ đọc chuỗi
``createmeta`` như một issue key nên trả HTTP 404 kèm ``Issue Does Not Exist`` — một thông báo
không liên quan gì tới nguyên nhân thật, đã tốn một vòng dò trên Jira production. Thay thế là
hai endpoint **có phân trang**:

- ``GET {API_PREFIX}/issue/createmeta/<KEY>/issuetypes`` — danh sách issue type;
- ``GET {API_PREFIX}/issue/createmeta/<KEY>/issuetypes/<ID>`` — field của một issue type.

Toàn bộ phần *dựng URL*, *gộp trang* và *định dạng* nằm ở đây để test được mà không mock
``urllib``; ``cli.py`` chỉ ghép chúng với một lời gọi ``client.request``.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from jira_tools.config import DEFAULT_API_PREFIX as API_PREFIX
from jira_tools.errors import JiraCliError

#: Gốc của cặp endpoint createmeta trên Jira 9 — dạng path, **không** phải query ``projectKeys``.
CREATEMETA_SUFFIX: Final = "/issue/createmeta"
ISSUE_TYPES_SEGMENT: Final = "issuetypes"
PAGE_START_PARAM: Final = "startAt"

#: Khoá gộp field vào bản ghi issue type (dùng cho cả ``--json`` lẫn phần hiển thị).
FIELDS_KEY: Final = "fields"

#: Trần số trang xin về cho mỗi danh sách. Một issue type thật có ~13 field và một project có
#: vài chục type, nên 100 trang × 50 phần tử là dư; trần tồn tại để một máy chủ trả ``isLast``
#: sai không làm CLI quay vòng vô hạn.
MAX_PAGES: Final = 100

UNKNOWN_LABEL: Final = "?"
MISSING_SCHEMA_TYPE: Final = "-"
SUBTASK_MARK: Final = "  [sub-task]"
DEFAULT_VALUE_MARK: Final = "  (có sẵn giá trị mặc định)"
FIELD_ID_COLUMN_WIDTH: Final = 22

#: Nhận ``startAt`` và trả nguyên trang JSON của Jira (hoặc ``None`` khi body rỗng).
PageFetcher = Callable[[int], Any]


def _paged(path: str, start_at: int) -> str:
    """Trang đầu giữ URL trần — dễ đọc trong log và trùng đúng URL người ta gõ tay."""
    if start_at <= 0:
        return path
    return f"{path}?{urllib.parse.urlencode({PAGE_START_PARAM: start_at})}"


def issue_types_path(project_key: str, start_at: int = 0, api_prefix: str = API_PREFIX) -> str:
    """``/rest/api/2/issue/createmeta/<KEY>/issuetypes`` — project key nằm trong **path**."""
    key = urllib.parse.quote(str(project_key), safe="")
    return _paged(f"{api_prefix}{CREATEMETA_SUFFIX}/{key}/{ISSUE_TYPES_SEGMENT}", start_at)


def issue_type_fields_path(
    project_key: str, issue_type_id: str, start_at: int = 0, api_prefix: str = API_PREFIX
) -> str:
    """``/rest/api/2/issue/createmeta/<KEY>/issuetypes/<ID>`` — field của một issue type."""
    key = urllib.parse.quote(str(project_key), safe="")
    type_id = urllib.parse.quote(str(issue_type_id), safe="")
    path = f"{api_prefix}{CREATEMETA_SUFFIX}/{key}/{ISSUE_TYPES_SEGMENT}/{type_id}"
    return _paged(path, start_at)


def _page_values(page: Any) -> list[dict[str, Any]]:
    if not isinstance(page, Mapping):
        return []
    return [dict(value) for value in page.get("values") or () if isinstance(value, Mapping)]


def _page_start(page: Any, fallback: int) -> int:
    """``startAt`` do máy chủ báo lại; dùng số của mình khi máy chủ không trả hoặc trả sai kiểu."""
    raw = page.get(PAGE_START_PARAM) if isinstance(page, Mapping) else None
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else fallback


def collect_pages(fetch: PageFetcher, *, max_pages: int = MAX_PAGES) -> list[dict[str, Any]]:
    """Gộp mọi trang ``values`` lại, lặp theo ``startAt`` cho tới khi ``isLast``.

    Không tin ``total`` ≤ ``maxResults``: project nhỏ hiện tại vừa đúng một trang, project khác
    thì không. Mặc định ``isLast`` là ``True`` để một máy chủ không trả khoá đó dừng ngay thay
    vì lặp mãi.
    """
    collected: list[dict[str, Any]] = []
    start_at = 0
    for _ in range(max_pages):
        page = fetch(start_at)
        values = _page_values(page)
        collected.extend(values)
        if not isinstance(page, Mapping) or page.get("isLast", True) or not values:
            return collected
        next_start = _page_start(page, start_at) + len(values)
        if next_start <= start_at:  # máy chủ không tiến ⇒ dừng, đừng quay vòng
            return collected
        start_at = next_start
    raise JiraCliError(f"Jira trả quá {max_pages} trang cho createmeta — dừng để khỏi lặp vô hạn.")


@dataclass(frozen=True)
class MetaField:
    """Một field trong createmeta, đã rút gọn về đúng phần người tạo issue cần biết."""

    field_id: str
    name: str
    schema_type: str
    required: bool
    has_default: bool


@dataclass(frozen=True)
class IssueTypeMeta:
    id: str
    name: str
    subtask: bool
    fields: tuple[MetaField, ...]

    @property
    def required_fields(self) -> tuple[MetaField, ...]:
        return tuple(field for field in self.fields if field.required)


def merge_issue_type(
    issue_type: Mapping[str, Any], fields: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Bản ghi gộp dùng chung cho ``--json`` và phần hiển thị, để khoá ``fields`` chỉ có một chỗ."""
    return {**dict(issue_type), FIELDS_KEY: [dict(field) for field in fields]}


def parse_field(raw: Mapping[str, Any]) -> MetaField:
    schema = raw.get("schema")
    schema_type = schema.get("type") if isinstance(schema, Mapping) else None
    return MetaField(
        field_id=str(raw.get("fieldId") or UNKNOWN_LABEL),
        name=str(raw.get("name") or UNKNOWN_LABEL),
        schema_type=str(schema_type or MISSING_SCHEMA_TYPE),
        required=bool(raw.get("required")),
        has_default=bool(raw.get("hasDefaultValue")),
    )


def parse_issue_type(raw: Mapping[str, Any]) -> IssueTypeMeta:
    """Bản ghi đã gộp (``merge_issue_type``) → dataclass để hiển thị."""
    fields = raw.get(FIELDS_KEY) or ()
    return IssueTypeMeta(
        id=str(raw.get("id") or UNKNOWN_LABEL),
        name=str(raw.get("name") or UNKNOWN_LABEL),
        subtask=bool(raw.get("subtask")),
        fields=tuple(parse_field(field) for field in fields if isinstance(field, Mapping)),
    )


def select_issue_types(
    issue_types: Sequence[Mapping[str, Any]], wanted_name: str | None
) -> list[dict[str, Any]]:
    """Lọc theo ``--type`` (không phân biệt hoa thường); không khớp thì liệt kê tên hợp lệ."""
    rows = [dict(row) for row in issue_types]
    if not wanted_name:
        return rows
    wanted = wanted_name.strip().casefold()
    matched = [row for row in rows if str(row.get("name", "")).strip().casefold() == wanted]
    if matched:
        return matched
    listing = "\n".join(f"  - {row.get('name', UNKNOWN_LABEL)}" for row in rows)
    raise JiraCliError(f"Không có issue type nào tên {wanted_name!r}. Đang có:\n{listing}")


def _render_field(field: MetaField) -> str:
    default = DEFAULT_VALUE_MARK if field.has_default else ""
    padded_id = field.field_id.ljust(FIELD_ID_COLUMN_WIDTH)
    return f"      required: {padded_id} {field.name} [{field.schema_type}]{default}"


def render_meta(project_key: str, issue_types: Sequence[IssueTypeMeta]) -> Iterator[str]:
    """Mỗi issue type một khối: id + tên, field bắt buộc, rồi toàn bộ field id dùng được."""
    yield f"{project_key}  ({len(issue_types)} issue type)"
    for issue_type in issue_types:
        yield ""
        subtask = SUBTASK_MARK if issue_type.subtask else ""
        yield f"  - {issue_type.name} (id={issue_type.id}){subtask}"
        required = issue_type.required_fields
        if not required:
            yield "      (không field nào bắt buộc)"
        for field in required:
            yield _render_field(field)
        available = ", ".join(field.field_id for field in issue_type.fields)
        yield f"      field dùng được: {available or '-'}"
