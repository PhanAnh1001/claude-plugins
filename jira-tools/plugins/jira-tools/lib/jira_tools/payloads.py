"""Hàm thuần dựng payload REST v2 và chọn transition — không chạm mạng, không đọc env.

Tách khỏi tầng HTTP để test được mà không phải mock ``urllib``: mọi quyết định về *hình dạng*
body (Jira Server dùng ``{"name": ...}`` cho assignee/priority, ``description`` là chuỗi thường
chứ không phải ADF) nằm gọn ở đây.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from jira_tools.errors import ConfigError, TransitionNotFound

DEFAULT_ISSUE_TYPE: Final = "Task"


def coerce_field_value(raw: str) -> Any:
    """JSON hợp lệ thì giữ kiểu JSON, còn lại coi là chuỗi.

    Nhờ vậy ``--field customfield_1={"value":"A"}`` gửi được object/mảng, còn
    ``--field customfield_2=Ghi chú`` vẫn gửi được chuỗi thường.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_field_assignments(assignments: Sequence[str] | None) -> dict[str, Any]:
    """``["a=1", "b=x"]`` → ``{"a": 1, "b": "x"}``; sai dạng thì hỏng tử tế."""
    fields: dict[str, Any] = {}
    for raw in assignments or ():
        key, separator, value = raw.partition("=")
        if not separator or not key.strip():
            raise ConfigError(f"--field phải có dạng KEY=VALUE, nhận được: {raw!r}")
        fields[key.strip()] = coerce_field_value(value)
    return fields


def _apply_optional_fields(
    payload: dict[str, Any],
    *,
    summary: str | None,
    description: str | None,
    labels: Sequence[str],
    assignee: str | None,
    priority: str | None,
) -> None:
    """Chỉ đặt field thật sự được truyền — với Jira, gửi ``null`` nghĩa là *xoá* giá trị."""
    if summary is not None:
        payload["summary"] = summary
    if description is not None:
        payload["description"] = description
    if labels:
        payload["labels"] = list(labels)
    if assignee is not None:
        # Jira Server định danh người dùng bằng ``name``; ``accountId`` là của Cloud.
        payload["assignee"] = {"name": assignee}
    if priority is not None:
        payload["priority"] = {"name": priority}


def build_create_payload(
    *,
    project: str,
    summary: str,
    issue_type: str = DEFAULT_ISSUE_TYPE,
    description: str | None = None,
    labels: Sequence[str] = (),
    assignee: str | None = None,
    priority: str | None = None,
    parent: str | None = None,
    fields: Mapping[str, Any] | None = None,
    create_defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Body cho ``POST /rest/api/2/issue``. ``fields`` ghi đè sau cùng, để ép được field lạ.

    ``create_defaults`` là luật riêng của từng dự án (``config/jira.json``), đặt trước các cờ
    truyền tay nên cờ luôn thắng. Ví dụ PROJ khai ``{"assignee": null}``: không truyền
    ``--assignee`` nghĩa là **chưa giao cho ai** — PROJ có default assignee là project lead, nên
    bỏ trống field này vẫn ra issue gán sẵn cho người khác; ``null`` tường minh mới giữ ô trống.
    """
    payload: dict[str, Any] = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
    }
    payload.update(create_defaults or {})
    _apply_optional_fields(
        payload,
        summary=summary,
        description=description,
        labels=labels,
        assignee=assignee,
        priority=priority,
    )
    if parent is not None:
        payload["parent"] = {"key": parent}
    payload.update(fields or {})
    return {"fields": payload}


def build_update_payload(
    *,
    summary: str | None = None,
    description: str | None = None,
    labels: Sequence[str] = (),
    assignee: str | None = None,
    priority: str | None = None,
    fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Body cho ``PUT /rest/api/2/issue/<KEY>``, chỉ gồm field được truyền."""
    payload: dict[str, Any] = {}
    _apply_optional_fields(
        payload,
        summary=summary,
        description=description,
        labels=labels,
        assignee=assignee,
        priority=priority,
    )
    payload.update(fields or {})
    return {"fields": payload}


def build_transition_payload(transition_id: str, comment: str | None = None) -> dict[str, Any]:
    """Body cho ``POST /rest/api/2/issue/<KEY>/transitions`` (kèm comment nếu có).

    CLI **không** truyền ``comment`` vào đây: Jira Server bỏ qua lặng lẽ ``update.comment`` khi
    transition không có screen — ``cli.cmd_transition`` đăng comment qua endpoint riêng.
    """
    payload: dict[str, Any] = {"transition": {"id": str(transition_id)}}
    if comment is not None:
        payload["update"] = {"comment": [{"add": {"body": comment}}]}
    return payload


def transition_label(transition: Mapping[str, Any]) -> str:
    """``"31  Bắt đầu → In Progress"`` — đủ để người đọc gõ lại đúng tên."""
    target = transition.get("to") or {}
    name = transition.get("name", "?")
    return f"{transition.get('id', '?')}  {name} → {target.get('name', '?')}"


def select_transition(
    transitions: Sequence[Mapping[str, Any]], target_name: str
) -> Mapping[str, Any]:
    """Khớp không phân biệt hoa thường với tên transition **hoặc** tên trạng thái đích.

    Hai tên đó thường khác nhau (transition "Start Progress" dẫn tới trạng thái "In Progress"),
    và người gõ lệnh nhớ tên trạng thái nhiều hơn tên transition, nên chấp nhận cả hai.
    """
    wanted = target_name.strip().casefold()
    for transition in transitions:
        target = transition.get("to") or {}
        names = {
            str(transition.get("name", "")).strip().casefold(),
            str(target.get("name", "")).strip().casefold(),
        }
        if wanted and wanted in names:
            return transition
    raise TransitionNotFound(target_name, [transition_label(t) for t in transitions])
