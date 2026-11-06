"""Thu dữ liệu cho lệnh ``report``: gọi Jira (search) và ``git log``, gom thành danh sách issue.

Mỗi issue là một dict thuần (in thẳng ra ``--json``) với các khoá ở ``issue_record``.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Final

from jira_tools.client import JiraClient
from jira_tools.report_period import (
    Commit,
    Period,
    commits_by_key,
    key_sort_value,
    keys_jql,
    plan_jql,
    resolved_jql,
    worklog_jql,
)

#: Tên hiển thị của field epic trên Jira Server; dùng khi config không khai ``epic_link``.
EPIC_LINK_NAME: Final = "Epic Link"
EPIC_LINK_CONFIG_KEY: Final = "epic_link"
BASE_FIELDS: Final = ("summary", "status", "issuetype", "labels", "timetracking", "resolutiondate")

SOURCE_WORKLOG: Final = "worklog"
SOURCE_RESOLVED: Final = "resolved"
SOURCE_COMMIT: Final = "commit"

SECONDS_PER_HOUR: Final = 3600
GIT_TIMEOUT_SECONDS: Final = 30.0
#: Mỗi lô ``key in (...)`` tối đa bấy nhiêu key, để JQL không quá dài.
KEYS_PER_QUERY: Final = 50


@dataclass
class ReportContext:
    """Tham số chung của một lần chạy ``report``."""

    client: JiraClient
    project: str
    user: str | None
    limit: int
    epic_field: str | None = None
    exclude_epics: Sequence[str] = ()
    epic_names: dict[str, str] = field(default_factory=dict)

    def fields(self) -> list[str]:
        return [*BASE_FIELDS, *([self.epic_field] if self.epic_field else [])]


def search_all(ctx: ReportContext, jql: str) -> list[dict[str, Any]]:
    """Search có phân trang theo ``startAt`` tới khi lấy đủ ``total``."""
    issues: list[dict[str, Any]] = []
    while True:
        body = {"jql": jql, "maxResults": ctx.limit, "fields": ctx.fields(), "startAt": len(issues)}
        page = ctx.client.request("POST", ctx.client.api("/search"), body) or {}
        batch = list(page.get("issues") or [])
        issues.extend(batch)
        if not batch or len(issues) >= int(page.get("total") or 0):
            return issues


def resolve_epic_field(client: JiraClient, project_fields: Mapping[str, str]) -> str | None:
    """``fields.epic_link`` trong config, không có thì tra ``GET /field`` theo tên."""
    configured = project_fields.get(EPIC_LINK_CONFIG_KEY)
    if configured:
        return configured
    for item in client.request("GET", client.api("/field")) or []:
        if isinstance(item, dict) and item.get("name") == EPIC_LINK_NAME:
            return str(item.get("id"))
    return None


def resolve_title(client: JiraClient, project: str, report_config: Mapping[str, Any]) -> str:
    title = report_config.get("title")
    if title:
        return str(title)
    body = client.request("GET", client.api(f"/project/{project}")) or {}
    return str(body.get("name") or project)


def _name(value: Any) -> str:
    return str(value.get("name", "")) if isinstance(value, dict) else ""


def issue_record(raw: Mapping[str, Any], epic_field: str | None) -> dict[str, Any]:
    fields = raw.get("fields") or {}
    status = fields.get("status") or {}
    tracking = fields.get("timetracking") or {}
    category = status.get("statusCategory") or {}
    return {
        "key": str(raw.get("key", "")),
        "summary": str(fields.get("summary") or ""),
        "status": _name(status),
        "status_category": str(category.get("key") or ""),
        "issuetype": _name(fields.get("issuetype")),
        "labels": list(fields.get("labels") or []),
        "epic": (fields.get(epic_field) if epic_field else None) or None,
        "epic_name": None,
        "original_estimate_seconds": tracking.get("originalEstimateSeconds"),
        "remaining_estimate_seconds": tracking.get("remainingEstimateSeconds"),
        "resolutiondate": fields.get("resolutiondate"),
        "sources": [],
        "commits": [],
    }


def _chunks(keys: Sequence[str]) -> Iterable[Sequence[str]]:
    for start in range(0, len(keys), KEYS_PER_QUERY):
        yield keys[start : start + KEYS_PER_QUERY]


def _merge(target: dict[str, dict[str, Any]], raws: Iterable[Mapping[str, Any]],
           ctx: ReportContext, source: str) -> None:
    for raw in raws:
        record = target.setdefault(str(raw.get("key", "")), issue_record(raw, ctx.epic_field))
        if source not in record["sources"]:
            record["sources"].append(source)


def fill_epic_names(ctx: ReportContext, issues: Iterable[dict[str, Any]]) -> None:
    """Một JQL ``key in (...)`` (theo lô) lấy summary của mọi epic; cache trong ``ctx``."""
    records = list(issues)
    missing = sorted({r["epic"] for r in records if r["epic"]} - set(ctx.epic_names))
    for chunk in _chunks(missing):
        for raw in search_all(ctx, keys_jql(chunk, exclude_epic_type=False)):
            ctx.epic_names[str(raw.get("key"))] = str((raw.get("fields") or {}).get("summary", ""))
    for record in records:
        record["epic_name"] = ctx.epic_names.get(record["epic"]) if record["epic"] else None


def _sorted(records: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [records[key] for key in sorted(records, key=key_sort_value)]


def _commit_dicts(commits: Sequence[Commit]) -> list[dict[str, str]]:
    return [{"date": c.day, "subject": c.subject} for c in commits]


def collect_done(ctx: ReportContext, period: Period, git_lines: Sequence[str]) -> list[dict]:
    """Hợp ba nguồn: worklog trong kỳ, resolved trong kỳ, key nhắc trong commit."""
    records: dict[str, dict[str, Any]] = {}
    _merge(records, search_all(ctx, worklog_jql(ctx.project, ctx.user, period)), ctx,
           SOURCE_WORKLOG)
    _merge(records, search_all(ctx, resolved_jql(ctx.project, ctx.user, period)), ctx,
           SOURCE_RESOLVED)
    by_key = commits_by_key(git_lines, ctx.project, period)
    commit_keys = sorted(by_key, key=key_sort_value)
    for chunk in _chunks(commit_keys):
        _merge(records, search_all(ctx, keys_jql(chunk)), ctx, SOURCE_COMMIT)
    for key, commits in by_key.items():
        if key in records:
            records[key]["commits"] = _commit_dicts(commits)
    fill_epic_names(ctx, records.values())
    return _sorted(records)


def collect_plan(ctx: ReportContext) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    _merge(records, search_all(ctx, plan_jql(ctx.project, ctx.user, ctx.exclude_epics)), ctx,
           "plan")
    for record in records.values():
        record["sources"] = []
    fill_epic_names(ctx, records.values())
    return _sorted(records)


def remaining_hours(issues: Iterable[Mapping[str, Any]]) -> float:
    seconds = sum(int(i.get("remaining_estimate_seconds") or 0) for i in issues)
    return round(seconds / SECONDS_PER_HOUR, 1)


def warn(message: str) -> None:
    print(f"cảnh báo: {message}", file=sys.stderr)


def _run_git(args: list[str]) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        warn(f"không chạy được git ({type(error).__name__}); bỏ qua nguồn commit")
        return None
    return done.stdout if done.returncode == 0 else None


def is_git_repo(repo: str) -> bool:
    return _run_git(["-C", repo, "rev-parse", "--git-dir"]) is not None


def git_author(repo: str) -> str | None:
    output = _run_git(["-C", repo, "config", "user.name"])
    return output.strip() or None if output else None


def read_git_log(repo: str, author: str | None, period: Period) -> list[str]:
    """Dòng ``ngày<TAB>subject`` trong kỳ; repo hỏng/thiếu git thì cảnh báo và trả rỗng."""
    if not is_git_repo(repo):
        warn(f"{repo} không phải git repo (hoặc thiếu git); bỏ qua nguồn commit")
        return []
    until = period.end + timedelta(days=1)
    args = ["-C", repo, "log", "--all", "--no-merges", f"--since={period.start}T00:00",
            f"--until={until}T00:00", "--format=%ad%x09%s", "--date=short"]
    name = author or git_author(repo)
    if name:
        args.append(f"--author={name}")
    output = _run_git(args)
    if output is None:
        warn(f"git log thất bại ở {repo}; bỏ qua nguồn commit")
        return []
    return [line for line in output.splitlines() if line.strip()]
