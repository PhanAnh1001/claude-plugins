"""Phần thuần của lệnh ``report``: khoảng ngày theo tuần, dựng JQL và trích key từ commit.

Tuần báo cáo neo vào thứ Sáu: "đã làm" là thứ Sáu tuần trước → thứ Sáu tuần này (cả hai đầu),
"sẽ làm" là thứ Sáu tuần này → thứ Năm tuần sau.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

from jira_tools.errors import ConfigError

#: ``date.weekday()`` của thứ Sáu (thứ Hai = 0).
FRIDAY: Final = 4
DAYS_PER_WEEK: Final = 7
#: Kỳ "sẽ làm" kết thúc thứ Năm tuần sau = thứ Sáu + 6 ngày.
PLAN_LENGTH_DAYS: Final = 6
DATE_FORMAT: Final = "%Y-%m-%d"
#: JQL chỉ lọc người dùng hiện tại khi không truyền ``--user``.
CURRENT_USER: Final = "currentUser()"
#: Tên field epic trong JQL (Jira Server, kể cả khi id customfield khác nhau giữa các host).
EPIC_LINK_JQL: Final = '"Epic Link"'


@dataclass(frozen=True)
class Period:
    """Khoảng ngày khép kín hai đầu."""

    start: date
    end: date

    def as_dict(self) -> dict[str, str]:
        return {"from": self.start.isoformat(), "to": self.end.isoformat()}


def parse_day(raw: str, flag: str) -> date:
    """``YYYY-MM-DD`` → ``date``; sai định dạng thì ``ConfigError`` (mã thoát 2)."""
    try:
        return datetime.strptime(raw.strip(), DATE_FORMAT).date()
    except ValueError:
        raise ConfigError(f"{flag} phải có dạng YYYY-MM-DD, nhận: {raw!r}") from None


def last_friday(anchor: date) -> date:
    """Thứ Sáu gần nhất không sau ``anchor`` (anchor là thứ Sáu thì chính nó)."""
    return anchor - timedelta(days=(anchor.weekday() - FRIDAY) % DAYS_PER_WEEK)


def done_period(anchor: date) -> Period:
    friday = last_friday(anchor)
    return Period(friday - timedelta(days=DAYS_PER_WEEK), friday)


def plan_period(anchor: date) -> Period:
    friday = last_friday(anchor)
    return Period(friday, friday + timedelta(days=PLAN_LENGTH_DAYS))


def user_clause(user: str | None) -> str:
    """Username dạng chuỗi JQL có nháy; không truyền thì ``currentUser()``."""
    if not user:
        return CURRENT_USER
    escaped = user.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _base(project: str) -> str:
    return f"project = {project} AND issuetype != Epic"


def worklog_jql(project: str, user: str | None, period: Period) -> str:
    return (
        f"{_base(project)} AND worklogAuthor = {user_clause(user)} "
        f'AND worklogDate >= "{period.start}" AND worklogDate <= "{period.end}"'
    )


def resolved_jql(project: str, user: str | None, period: Period) -> str:
    """``resolved < to+1`` để gồm trọn ngày cuối (``resolved`` có cả giờ)."""
    day_after = period.end + timedelta(days=1)
    return (
        f"{_base(project)} AND assignee = {user_clause(user)} "
        f'AND resolved >= "{period.start}" AND resolved < "{day_after}"'
    )


def plan_jql(project: str, user: str | None, exclude_epics: Sequence[str] = ()) -> str:
    jql = f"{_base(project)} AND statusCategory != Done AND assignee = {user_clause(user)}"
    if exclude_epics:
        keys = ", ".join(exclude_epics)
        jql += f" AND ({EPIC_LINK_JQL} is EMPTY OR {EPIC_LINK_JQL} not in ({keys}))"
    return jql


def keys_jql(keys: Sequence[str], exclude_epic_type: bool = True) -> str:
    jql = f"key in ({', '.join(keys)})"
    return f"{jql} AND issuetype != Epic" if exclude_epic_type else jql


def key_pattern(project: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(project)}-\d+\b")


@dataclass(frozen=True)
class Commit:
    day: str
    subject: str


def parse_commit_line(line: str) -> Commit | None:
    """Dòng ``%ad%x09%s`` (ngày short, tab, subject); dòng hỏng thì ``None``."""
    day, sep, subject = line.partition("\t")
    if not sep or not day.strip():
        return None
    return Commit(day.strip(), subject.strip())


def _within(day: str, period: Period) -> bool:
    """So chuỗi ``YYYY-MM-DD`` (cùng định dạng ``--date=short`` của git) với hai đầu kỳ."""
    return period.start.isoformat() <= day <= period.end.isoformat()


def commits_by_key(
    lines: Sequence[str], project: str, period: Period | None = None
) -> dict[str, list[Commit]]:
    """Gom commit theo key Jira nhắc trong subject; một commit có thể thuộc nhiều key.

    Có ``period`` thì bỏ commit có ngày tác giả nằm ngoài kỳ: ``git log --since`` lọc theo ngày
    commit, nên commit viết hôm trước rồi rebase/cherry-pick vào kỳ vẫn lọt qua git.
    """
    pattern = key_pattern(project)
    grouped: dict[str, list[Commit]] = {}
    for line in lines:
        commit = parse_commit_line(line)
        if commit is None:
            continue
        if period is not None and not _within(commit.day, period):
            continue
        for key in dict.fromkeys(pattern.findall(commit.subject)):
            grouped.setdefault(key, []).append(commit)
    for commits in grouped.values():
        commits.sort(key=lambda c: c.day)
    return grouped


def key_sort_value(key: str) -> tuple[str, int]:
    """``PROJ-9`` < ``PROJ-10``: so phần số theo số nguyên."""
    prefix, _, number = key.rpartition("-")
    return (prefix, int(number)) if number.isdigit() else (key, 0)
