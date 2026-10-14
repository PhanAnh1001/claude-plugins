"""Lệnh ``worklog``: log thời gian thật vào issue, tuỳ chọn đặt luôn remaining estimate.

Dùng endpoint riêng ``POST /issue/<KEY>/worklog`` chứ không đi qua ``update.worklog`` của
transition: transition của PROJ không có screen (``fields = {}``) nên Jira Server bỏ qua lặng lẽ
phần ``update`` — đúng kiểu lỗi đã gặp với ``update.comment``. Remaining estimate đi theo query
``adjustEstimate=new&newEstimate=...`` nên không phụ thuộc field ``timetracking`` có trên screen
hay không. Sau khi ghi, lệnh đọc lại ``timetracking`` và thoát khác 0 nếu không khớp.
"""

from __future__ import annotations

import argparse
import re
import urllib.parse
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

from jira_tools.client import JiraClient
from jira_tools.errors import EXIT_OK, ConfigError, WorklogNotVerified
from jira_tools.output import dry_run, print_json

#: Định dạng ``started`` mà Jira Server chấp nhận, ví dụ ``2026-09-25T09:00:00.000+0700``.
JIRA_STARTED_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.000%z"

#: Số giây của mỗi đơn vị thời lượng Jira. ``d``/``w`` theo cấu hình time tracking của server
#: (đo trên host công ty 2026-09: ``workingHoursPerDay 8``, ``workingDaysPerWeek 5`` — cũng là
#: mặc định của Jira); chỉ dùng để so khớp khi đọc lại, chuỗi gửi lên vẫn giữ nguyên đơn vị.
SECONDS_PER_MINUTE: Final = 60
SECONDS_PER_HOUR: Final = 60 * SECONDS_PER_MINUTE
WORKING_HOURS_PER_DAY: Final = 8
WORKING_DAYS_PER_WEEK: Final = 5
UNIT_SECONDS: Final[dict[str, int]] = {
    "m": SECONDS_PER_MINUTE,
    "h": SECONDS_PER_HOUR,
    "d": WORKING_HOURS_PER_DAY * SECONDS_PER_HOUR,
    "w": WORKING_DAYS_PER_WEEK * WORKING_HOURS_PER_DAY * SECONDS_PER_HOUR,
}
#: Mỗi phần là ``<số nguyên><đơn vị>``; cho phép viết liền (``1h30m``) hoặc cách (``1h 30m``).
DURATION_PART: Final = re.compile(r"(\d+)\s*([wdhm])")
DURATION_FULL: Final = re.compile(r"\s*(?:\d+\s*[wdhm]\s*)+")

#: Giá trị query ``adjustEstimate``: ``new`` đặt remaining theo ``newEstimate``; ``auto`` để Jira
#: tự trừ thời gian vừa log khỏi remaining hiện có.
ADJUST_NEW: Final = "new"
ADJUST_AUTO: Final = "auto"

TIME_HELP: Final = "thời lượng định dạng Jira: 30m, 2h, 1h30m, 1d (đơn vị w/d/h/m)"


def normalize_duration(raw: str, flag: str) -> str:
    """``"1h30m"`` → ``"1h 30m"``; sai định dạng Jira thì ``ConfigError`` (mã thoát 2)."""
    if not DURATION_FULL.fullmatch(raw):
        raise ConfigError(f"{flag} phải theo định dạng Jira (w/d/h/m, ví dụ 1h30m), nhận: {raw!r}")
    return " ".join(f"{number}{unit}" for number, unit in DURATION_PART.findall(raw))


def _optional_duration(raw: str | None, flag: str) -> str | None:
    """Cờ không truyền ⇒ ``None``; truyền (kể cả chuỗi rỗng) ⇒ phải hợp lệ."""
    return None if raw is None else normalize_duration(raw, flag)


def duration_seconds(duration: str) -> int:
    """Số giây của chuỗi đã chuẩn hoá — dùng để so với ``remainingEstimateSeconds``."""
    return sum(int(number) * UNIT_SECONDS[unit] for number, unit in DURATION_PART.findall(duration))


def format_started(raw: str | None, now: datetime | None = None) -> str:
    """``started`` theo định dạng Jira; bỏ trống thì lấy giờ hiện tại theo timezone máy.

    Nhận cả định dạng Jira (``...000+0700``) lẫn ISO 8601 (``2026-09-25T09:00+07:00``,
    ``2026-09-25``); thiếu múi giờ thì hiểu là giờ địa phương của máy.
    """
    moment = (now or datetime.now()) if raw is None else _parse_started(raw)
    if moment.tzinfo is None:
        moment = moment.astimezone()  # giờ "naive" ⇒ gắn timezone của máy
    return moment.strftime(JIRA_STARTED_FORMAT)


def _parse_started(raw: str) -> datetime:
    text = raw.strip()
    try:
        return datetime.strptime(text, JIRA_STARTED_FORMAT)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ConfigError(
            f"--started phải là ISO 8601 hoặc dạng Jira 2026-09-25T09:00:00.000+0700, nhận: {raw!r}"
        ) from None


def build_worklog_payload(
    time_spent: str, started: str, comment: str | None = None
) -> dict[str, Any]:
    """Body cho ``POST /rest/api/2/issue/<KEY>/worklog``; ``comment`` chỉ gửi khi có."""
    payload: dict[str, Any] = {"timeSpent": time_spent, "started": started}
    if comment is not None:
        payload["comment"] = comment
    return payload


def worklog_query(remaining: str | None) -> str:
    """Có ``remaining`` ⇒ đặt đúng giá trị đó; không có ⇒ để Jira tự trừ."""
    if remaining is None:
        return urllib.parse.urlencode({"adjustEstimate": ADJUST_AUTO})
    return urllib.parse.urlencode({"adjustEstimate": ADJUST_NEW, "newEstimate": remaining})


def _worklog_path(client: JiraClient, key: str) -> str:
    return client.api(f"/issue/{key}/worklog")


def _read_timetracking(client: JiraClient, key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"fields": "timetracking"})
    issue = client.request("GET", client.api(f"/issue/{key}?{query}")) or {}
    return dict((issue.get("fields") or {}).get("timetracking") or {})


def _verify_remaining(client: JiraClient, key: str, remaining: str) -> dict[str, Any]:
    """Đọc lại ``timetracking``; remaining lệch với giá trị yêu cầu thì ``WorklogNotVerified``."""
    tracking = _read_timetracking(client, key)
    stored = tracking.get("remainingEstimateSeconds")
    if stored is None or int(stored) != duration_seconds(remaining):
        raise WorklogNotVerified(
            key, f"remaining đọc lại là {tracking.get('remainingEstimate')!r}, cần {remaining!r}"
        )
    return tracking


def cmd_worklog(client: JiraClient, args: argparse.Namespace) -> int:
    time_spent = normalize_duration(args.time, "--time")
    remaining = _optional_duration(args.remaining, "--remaining")
    payload = build_worklog_payload(time_spent, format_started(args.started), args.comment)
    path = f"{_worklog_path(client, args.key)}?{worklog_query(remaining)}"
    if args.dry_run:
        dry_run("POST", client.url(path), payload)
        if remaining is not None:
            print(f"(sau đó GET timetracking của {args.key} để đọc lại remaining)")
        return EXIT_OK
    created = client.request("POST", path, payload) or {}
    worklog_id = str(created.get("id") or "")
    if not worklog_id:
        raise WorklogNotVerified(args.key, "Jira không trả id worklog")
    tracking = _verify_remaining(client, args.key, remaining) if remaining is not None else {}
    if args.json:
        print_json({"worklog": created, "timetracking": tracking})
        return EXIT_OK
    print(f"{args.key} đã log {time_spent} (worklog id={worklog_id})")
    if remaining is not None:
        print(f"{args.key} remaining {tracking.get('remainingEstimate')}")
    return EXIT_OK


def add_worklog_parser(
    subparsers: Any, parents: Sequence[argparse.ArgumentParser]
) -> argparse.ArgumentParser:
    """Đăng ký subcommand ``worklog`` vào parser của ``cli``."""
    parser = subparsers.add_parser("worklog", parents=list(parents), help="log thời gian vào issue")
    parser.add_argument("key")
    parser.add_argument("--time", required=True, help=TIME_HELP)
    parser.add_argument(
        "--started",
        help="lúc bắt đầu (ISO 8601); bỏ trống thì lấy giờ hiện tại theo timezone máy",
    )
    parser.add_argument("--comment", help="ghi chú của worklog")
    parser.add_argument(
        "--remaining",
        help="đặt remaining estimate sau khi log (ví dụ 0m khi chuyển Done); "
        "bỏ trống thì Jira tự trừ",
    )
    parser.set_defaults(handler=cmd_worklog)
    return parser
